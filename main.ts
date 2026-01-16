"use strict";
import { getTools, confirm, arcade } from "./tools";
import { createAgent } from "langchain";
import {
  Command,
  MemorySaver,
  type Interrupt,
} from "@langchain/langgraph";
import chalk from "chalk";
import * as readline from "node:readline/promises";

// configure your own values to customize your agent

// The Arcade User ID identifies who is authorizing each service.
const arcadeUserID = process.env.ARCADE_USER_ID;
if (!arcadeUserID) {
  throw new Error("Missing ARCADE_USER_ID. Add it to your .env file.");
}
// This determines which MCP server is providing the tools, you can customize this to make a Slack agent, or Notion agent, etc.
// all tools from each of these MCP servers will be retrieved from arcade
const toolkits=['Gmail'];
// This determines isolated tools that will be
const isolatedTools=[];
// This determines the maximum number of tool definitions Arcade will return
const toolLimit = 100;
// This prompt defines the behavior of the agent.
const systemPrompt = "# Introduction\nThis AI agent is designed to assist users in managing their Gmail accounts efficiently. It can perform a variety of tasks, including sending emails, organizing emails with labels, managing drafts, and searching through email threads. By leveraging various Gmail API tools, the agent streamlines email management processes and enhances productivity.\n\n# Instructions\n- Understand user requests related to Gmail functionalities.\n- Utilize the appropriate tool(s) to execute the required action based on user queries or commands.\n- Maintain a conversational interface, prompting the user for any necessary details or clarifications.\n- Ensure the sequence of operations is logical, especially when performing multiple steps.\n- Provide feedback or confirmation after completing actions.\n\n# Workflows\n### 1. Send an Email\n**Tools Used:** `Gmail_SendEmail`\n- Input: subject, body, recipient, optional cc/bcc.\n- Process: Gather all required information from the user, construct the email and send it.\n\n### 2. List Emails\n**Tools Used:** `Gmail_ListEmails`\n- Input: number of emails (n_emails).\n- Process: Retrieve and display the specified number of recent emails to the user.\n\n### 3. Search for Emails\n**Tools Used:** `Gmail_ListEmailsByHeader` or `Gmail_SearchThreads`\n- Input: parameters such as sender, subject, date_range, etc.\n- Process: Use specified search criteria to find relevant emails and display results to the user.\n\n### 4. Create a Label\n**Tools Used:** `Gmail_CreateLabel`\n- Input: label_name.\n- Process: Prompt user for a name for the new label, create it in the user\u0027s mailbox.\n\n### 5. Add/Remove Labels from an Email\n**Tools Used:** `Gmail_ChangeEmailLabels`\n- Input: email_id, labels_to_add, labels_to_remove.\n- Process: Prompt user for the email ID and the labels to modify, then execute the changes.\n\n### 6. Manage Draft Emails\n**Sub-Workflows:**\n- **List Draft Emails:** `Gmail_ListDraftEmails` - Get draft emails and display them.\n- **Write a Draft Email:** `Gmail_WriteDraftEmail` - Prompt user for subject, body, and recipient to create a new draft.\n- **Update a Draft Email:** `Gmail_UpdateDraftEmail` - Gather details from user to modify an existing draft.\n- **Send a Draft Email:** `Gmail_SendDraftEmail` - Send a specified draft based on draft ID.\n- **Delete a Draft Email:** `Gmail_DeleteDraftEmail` - Request draft ID from user and delete the specified draft.\n\n### 7. Reply to an Email\n**Tools Used:** `Gmail_ReplyToEmail`\n- Input: reply_to_message_id, body, optional reply_to_whom, cc/bcc.\n- Process: Gather required data for replying to the specified email.\n\n### 8. Move Email to Trash\n**Tools Used:** `Gmail_TrashEmail`\n- Input: email_id.\n- Process: Ask for the email ID that needs to be trashed and execute the command.\n\n### 9. Retrieve User Profile\n**Tools Used:** `Gmail_WhoAmI`\n- Process: Retrieve and display comprehensive user profile and account information to the user.\n\nThis structured approach allows the agent to efficiently respond to user requests, ensuring a smooth email management experience.";
// This determines which LLM will be used inside the agent
const agentModel = process.env.OPENAI_MODEL;
if (!agentModel) {
  throw new Error("Missing OPENAI_MODEL. Add it to your .env file.");
}
// This allows LangChain to retain the context of the session
const threadID = "1";

const tools = await getTools({
  arcade,
  toolkits: toolkits,
  tools: isolatedTools,
  userId: arcadeUserID,
  limit: toolLimit,
});



async function handleInterrupt(
  interrupt: Interrupt,
  rl: readline.Interface
): Promise<{ authorized: boolean }> {
  const value = interrupt.value;
  const authorization_required = value.authorization_required;
  const hitl_required = value.hitl_required;
  if (authorization_required) {
    const tool_name = value.tool_name;
    const authorization_response = value.authorization_response;
    console.log("⚙️: Authorization required for tool call", tool_name);
    console.log(
      "⚙️: Please authorize in your browser",
      authorization_response.url
    );
    console.log("⚙️: Waiting for you to complete authorization...");
    try {
      await arcade.auth.waitForCompletion(authorization_response.id);
      console.log("⚙️: Authorization granted. Resuming execution...");
      return { authorized: true };
    } catch (error) {
      console.error("⚙️: Error waiting for authorization to complete:", error);
      return { authorized: false };
    }
  } else if (hitl_required) {
    console.log("⚙️: Human in the loop required for tool call", value.tool_name);
    console.log("⚙️: Please approve the tool call", value.input);
    const approved = await confirm("Do you approve this tool call?", rl);
    return { authorized: approved };
  }
  return { authorized: false };
}

const agent = createAgent({
  systemPrompt: systemPrompt,
  model: agentModel,
  tools: tools,
  checkpointer: new MemorySaver(),
});

async function streamAgent(
  agent: any,
  input: any,
  config: any
): Promise<Interrupt[]> {
  const stream = await agent.stream(input, {
    ...config,
    streamMode: "updates",
  });
  const interrupts: Interrupt[] = [];

  for await (const chunk of stream) {
    if (chunk.__interrupt__) {
      interrupts.push(...(chunk.__interrupt__ as Interrupt[]));
      continue;
    }
    for (const update of Object.values(chunk)) {
      for (const msg of (update as any)?.messages ?? []) {
        console.log("🤖: ", msg.toFormattedString());
      }
    }
  }

  return interrupts;
}

async function main() {
  const config = { configurable: { thread_id: threadID } };
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log(chalk.green("Welcome to the chatbot! Type 'exit' to quit."));
  while (true) {
    const input = await rl.question("> ");
    if (input.toLowerCase() === "exit") {
      break;
    }
    rl.pause();

    try {
      let agentInput: any = {
        messages: [{ role: "user", content: input }],
      };

      // Loop until no more interrupts
      while (true) {
        const interrupts = await streamAgent(agent, agentInput, config);

        if (interrupts.length === 0) {
          break; // No more interrupts, we're done
        }

        // Handle all interrupts
        const decisions: any[] = [];
        for (const interrupt of interrupts) {
          decisions.push(await handleInterrupt(interrupt, rl));
        }

        // Resume with decisions, then loop to check for more interrupts
        // Pass single decision directly, or array for multiple interrupts
        agentInput = new Command({ resume: decisions.length === 1 ? decisions[0] : decisions });
      }
    } catch (error) {
      console.error(error);
    }

    rl.resume();
  }
  console.log(chalk.red("👋 Bye..."));
  process.exit(0);
}

// Run the main function
main().catch((err) => console.error(err));
from agents import (Agent, Runner, AgentHooks, Tool, RunContextWrapper,
                    TResponseInputItem,)
from functools import partial
from arcadepy import AsyncArcade
from agents_arcade import get_arcade_tools
from typing import Any
from human_in_the_loop import (UserDeniedToolCall,
                               confirm_tool_usage,
                               auth_tool)

import globals


class CustomAgentHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.event_counter = 0
        self.display_name = display_name

    async def on_start(self,
                       context: RunContextWrapper,
                       agent: Agent) -> None:
        self.event_counter += 1
        print(f"### ({self.display_name}) {
              self.event_counter}: Agent {agent.name} started")

    async def on_end(self,
                     context: RunContextWrapper,
                     agent: Agent,
                     output: Any) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended with output {output}"
                agent.name} ended"
        )

    async def on_handoff(self,
                         context: RunContextWrapper,
                         agent: Agent,
                         source: Agent) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                source.name} handed off to {agent.name}"
        )

    async def on_tool_start(self,
                            context: RunContextWrapper,
                            agent: Agent,
                            tool: Tool) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}:"
            f" Agent {agent.name} started tool {tool.name}"
            f" with context: {context.context}"
        )

    async def on_tool_end(self,
                          context: RunContextWrapper,
                          agent: Agent,
                          tool: Tool,
                          result: str) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended tool {tool.name} with result {result}"
                agent.name} ended tool {tool.name}"
        )


async def main():

    context = {
        "user_id": os.getenv("ARCADE_USER_ID"),
    }

    client = AsyncArcade()

    arcade_tools = await get_arcade_tools(
        client, toolkits=["Gmail"]
    )

    for tool in arcade_tools:
        # - human in the loop
        if tool.name in ENFORCE_HUMAN_CONFIRMATION:
            tool.on_invoke_tool = partial(
                confirm_tool_usage,
                tool_name=tool.name,
                callback=tool.on_invoke_tool,
            )
        # - auth
        await auth_tool(client, tool.name, user_id=context["user_id"])

    agent = Agent(
        name="",
        instructions="# Introduction
This AI agent is designed to assist users in managing their Gmail accounts efficiently. It can perform a variety of tasks, including sending emails, organizing emails with labels, managing drafts, and searching through email threads. By leveraging various Gmail API tools, the agent streamlines email management processes and enhances productivity.

# Instructions
- Understand user requests related to Gmail functionalities.
- Utilize the appropriate tool(s) to execute the required action based on user queries or commands.
- Maintain a conversational interface, prompting the user for any necessary details or clarifications.
- Ensure the sequence of operations is logical, especially when performing multiple steps.
- Provide feedback or confirmation after completing actions.

# Workflows
### 1. Send an Email
**Tools Used:** `Gmail_SendEmail`
- Input: subject, body, recipient, optional cc/bcc.
- Process: Gather all required information from the user, construct the email and send it.

### 2. List Emails
**Tools Used:** `Gmail_ListEmails`
- Input: number of emails (n_emails).
- Process: Retrieve and display the specified number of recent emails to the user.

### 3. Search for Emails
**Tools Used:** `Gmail_ListEmailsByHeader` or `Gmail_SearchThreads`
- Input: parameters such as sender, subject, date_range, etc.
- Process: Use specified search criteria to find relevant emails and display results to the user.

### 4. Create a Label
**Tools Used:** `Gmail_CreateLabel`
- Input: label_name.
- Process: Prompt user for a name for the new label, create it in the user's mailbox.

### 5. Add/Remove Labels from an Email
**Tools Used:** `Gmail_ChangeEmailLabels`
- Input: email_id, labels_to_add, labels_to_remove.
- Process: Prompt user for the email ID and the labels to modify, then execute the changes.

### 6. Manage Draft Emails
**Sub-Workflows:**
- **List Draft Emails:** `Gmail_ListDraftEmails` - Get draft emails and display them.
- **Write a Draft Email:** `Gmail_WriteDraftEmail` - Prompt user for subject, body, and recipient to create a new draft.
- **Update a Draft Email:** `Gmail_UpdateDraftEmail` - Gather details from user to modify an existing draft.
- **Send a Draft Email:** `Gmail_SendDraftEmail` - Send a specified draft based on draft ID.
- **Delete a Draft Email:** `Gmail_DeleteDraftEmail` - Request draft ID from user and delete the specified draft.

### 7. Reply to an Email
**Tools Used:** `Gmail_ReplyToEmail`
- Input: reply_to_message_id, body, optional reply_to_whom, cc/bcc.
- Process: Gather required data for replying to the specified email.

### 8. Move Email to Trash
**Tools Used:** `Gmail_TrashEmail`
- Input: email_id.
- Process: Ask for the email ID that needs to be trashed and execute the command.

### 9. Retrieve User Profile
**Tools Used:** `Gmail_WhoAmI`
- Process: Retrieve and display comprehensive user profile and account information to the user.

This structured approach allows the agent to efficiently respond to user requests, ensuring a smooth email management experience.",
        model=os.environ["OPENAI_MODEL"],
        tools=arcade_tools,
        hooks=CustomAgentHooks(display_name="")
    )

    # initialize the conversation
    history: list[TResponseInputItem] = []
    # run the loop!
    while True:
        prompt = input("You: ")
        if prompt.lower() == "exit":
            break
        history.append({"role": "user", "content": prompt})
        try:
            result = await Runner.run(
                starting_agent=agent,
                input=history,
                context=context
            )
            history = result.to_input_list()
            print(result.final_output)
        except UserDeniedToolCall as e:
            history.extend([
                {"role": "assistant",
                 "content": f"Please confirm the call to {e.tool_name}"},
                {"role": "user",
                 "content": "I changed my mind, please don't do it!"},
                {"role": "assistant",
                 "content": f"Sure, I cancelled the call to {e.tool_name}."
                 " What else can I do for you today?"
                 },
            ])
            print(history[-1]["content"])

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
from arcadepy import AsyncArcade
from dotenv import load_dotenv
from google.adk import Agent, Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService, Session
from google_adk_arcade.tools import get_arcade_tools
from google.genai import types
from human_in_the_loop import auth_tool, confirm_tool_usage

import os

load_dotenv(override=True)


async def main():
    app_name = "my_agent"
    user_id = os.getenv("ARCADE_USER_ID")

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    client = AsyncArcade()

    agent_tools = await get_arcade_tools(
        client, toolkits=["Gmail"]
    )

    for tool in agent_tools:
        await auth_tool(client, tool_name=tool.name, user_id=user_id)

    agent = Agent(
        model=LiteLlm(model=f"openai/{os.environ["OPENAI_MODEL"]}"),
        name="google_agent",
        instruction="# Introduction
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
        description="An agent that uses Gmail tools provided to perform any task",
        tools=agent_tools,
        before_tool_callback=[confirm_tool_usage],
    )

    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, state={
            "user_id": user_id,
        }
    )
    runner = Runner(
        app_name=app_name,
        agent=agent,
        artifact_service=artifact_service,
        session_service=session_service,
    )

    async def run_prompt(session: Session, new_message: str):
        content = types.Content(
            role='user', parts=[types.Part.from_text(text=new_message)]
        )
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content.parts and event.content.parts[0].text:
                print(f'** {event.author}: {event.content.parts[0].text}')

    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        await run_prompt(session, user_input)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
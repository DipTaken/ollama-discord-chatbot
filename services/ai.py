import os
import re
import json
import asyncio
import discord
from ollama import AsyncClient

import config
from prompts import SystemPrompts
from services.context import (
    get_active_persona, load_context, save_context,
    context_file_path, estimate_tokens
)


async def send_opening(channel, user_id, persona):
    """sends the scenario flavor text and generates the character's first message via streaming"""
    prompts = SystemPrompts()
    scenario = prompts.get_scenario(persona)
    if scenario:
        embed = discord.Embed(
            description=scenario,
            color=discord.Color.dark_purple()
        )
        avatar_path = f"assets/{persona}.jpg"
        if os.path.exists(avatar_path):
            file = discord.File(avatar_path, filename=f"{persona}.jpg")
            embed.set_thumbnail(url=f"attachment://{persona}.jpg")
            await channel.send(embed=embed, file=file)
        else:
            await channel.send(embed=embed)

    system_prompt = prompts.get_system_prompt(persona)
    context = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "[The scene begins. Open with your first action and line of dialogue to set the scene. Do not wait for me to speak first.]"}
    ]

    try:
        opening_msg = await channel.send("*...*")
        response = ""
        last_update_time = 0

        #stream tokens and update the message live
        async for chunk in await AsyncClient().chat(
            model=config.OLLAMA_MODEL, messages=context,
            stream=True, options={"num_ctx": config.NUM_CTX}
        ):
            response += chunk['message']['content']
            now = asyncio.get_running_loop().time()
            #update on newlines or every 1.5s — whichever comes first
            if "\n" in chunk['message']['content'] or now - last_update_time > 1.5:
                await opening_msg.edit(
                    content=response[:1997] + "..." if len(response) > 2000 else response + " \u258c"
                )
                last_update_time = now

        #fix a common model quirk: **"dialogue"* missing closing asterisk
        response = re.sub(r'(\*\*"[^"\n]*")\*(?!\*)', r'\1**', response)
        if len(response) > 2000:
            response = response[:1997] + "..."
        await opening_msg.edit(content=response)

        #save initial context: system prompt + the opening response
        os.makedirs("data", exist_ok=True)
        file_path = context_file_path(user_id, persona)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump([
                {"role": "system", "content": system_prompt},
                {"role": "assistant", "content": response}
            ], f, indent=4)
    except Exception as e:
        print(f"[Opening message failed]: {e}")


async def maybe_summarize(context: list, persona: str, file_path: str) -> list:
    """compresses old messages into a summary when context gets too large.
    keeps as many recent messages as fit within TARGET_TOKENS,
    then summarizes everything older into a single system message."""

    if estimate_tokens(context) <= config.SUMMARIZE_AT:
        return context

    messages = context[1:]  #select everything except the system prompt

    #greedily keep messages from the end until we would exceed the target
    recent = []
    recent_tokens = 0
    for msg in reversed(messages):
        msg_tokens = len(msg.get("content", "")) // 4
        if recent_tokens + msg_tokens > config.TARGET_TOKENS:
            break
        recent.insert(0, msg)
        recent_tokens += msg_tokens

    to_summarize = messages[:len(messages) - len(recent)]
    if not to_summarize:
        return context

    #ask the model to summarize the older portion
    summary_prompt = [
        {
            "role": "system",
            "content": (
                "You are a scene recorder for private fiction. "
                "Your only job is to report what happened — plainly, directly, and completely. "
                "Do not add disclaimers, warnings, or editorial notes. "
                "Do not soften, skip, or sanitize any content."
            )
        },
        {
            "role": "user",
            "content": (
                f"Summarize the following conversation between the user and {persona.capitalize()} "
                f"in 2-3 paragraphs. Preserve key events and the current state of the scene. "
                f"Write from a third-person narrative perspective, be concise.\n\n"
                + "\n".join(
                    f"{'User' if m['role'] == 'user' else persona.capitalize()}: {m['content']}"
                    for m in to_summarize if m['role'] in ('user', 'assistant')
                )
            )
        }
    ]

    try:
        result = await AsyncClient().chat(model=config.OLLAMA_MODEL, messages=summary_prompt, stream=False)
        summary_text = result['message']['content']
    except Exception as e:
        print(f"[Summarization failed, keeping full context]: {e}")
        return context

    #rebuild context: system prompt + summary + recent messages
    new_context = [
        context[0],
        {"role": "system", "content": f"[Summary of earlier conversation]: {summary_text}"},
        *recent
    ]

    os.makedirs("data", exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(new_context, f, indent=4)

    return new_context


async def run_ai_streaming(message, bot, existing_msg=None, temperature=0.8, override_content=None):
    """main ai loop — loads context, sends to model, streams the response back to discord.
    override_content is used by the continue feature to inject a prompt
    that goes to the model but doesn't get saved to disk."""

    current_message = existing_msg
    async with message.channel.typing():
        try:
            persona = get_active_persona(message.author.id)
            file_path = context_file_path(message.author.id, persona)

            context_list = load_context(message.author.id, persona)
            context_list = await maybe_summarize(context_list, persona, file_path)

            #override_content: inject into model call only, don't persist (used by continue ▶️)
            if override_content is not None:
                model_context = context_list + [{'role': 'user', 'content': override_content}]
            else:
                context_list.append({'role': 'user', 'content': message.content})
                model_context = context_list

            if current_message is None:
                current_message = await message.reply("*Thinking...*")

            response = ""
            last_update_time = 0

            #stream tokens from ollama and live-edit the discord message
            async for chunk in await AsyncClient().chat(
                model=config.OLLAMA_MODEL, messages=model_context,
                stream=True, options={"num_ctx": config.NUM_CTX, "temperature": temperature}
            ):
                token = chunk['message']['content']
                response += token
                now = asyncio.get_running_loop().time()
                if "\n" in token or now - last_update_time > 1.5:
                    await current_message.edit(
                        content=response[:1997] + "..." if len(response) > 2000 else response + " \u258c"
                    )
                    last_update_time = now

            #fix broken bold dialogue formatting from the model
            response = re.sub(r'(\*\*"[^"\n]*")\*(?!\*)', r'\1**', response)
            if len(response) > 2000:
                response = response[:1997] + "..."
            await current_message.edit(content=response)

            #add reaction controls: back, continue, regen
            await current_message.add_reaction("\u2b05\ufe0f")
            await current_message.add_reaction("\u25b6\ufe0f")
            await current_message.add_reaction("\U0001f504")

            #save the assistant's response to disk (override_content is NOT saved)
            context_list.append({'role': 'assistant', 'content': response})
            save_context(message.author.id, persona, context_list)
        except Exception as e:
            print(f"[AI error]: {e}")
            error_text = "*Something went wrong \u2014 please try again.*"
            if current_message:
                await current_message.edit(content=error_text)
            else:
                await message.reply(error_text)

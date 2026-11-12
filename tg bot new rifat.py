import asyncio
import sys
import os
import time
import random
import glob
import json
import socks  # PySocks লাইব্রেরি প্রয়োজন (pip install PySocks)
from telethon import TelegramClient, events
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonChildAbuse,
    InputReportReasonCopyright,
    InputReportReasonGeoIrrelevant,
    InputReportReasonFake,
    InputReportReasonIllegalDrugs,
    InputReportReasonPersonalDetails,
    InputReportReasonOther
)
from colorama import Fore, Style, init

init(autoreset=True)

# --- CONFIGURATION ---
API_ID = 37745734          # আপনার API ID
API_HASH = 'a3451a8959597f48f2d56a4caf0861ab'  # আপনার API Hash
PROXY_FILE = "proxies.txt"
TOKEN_FILE = "tokens.txt"  # একাধিক বট টোকেন জমা রাখার ফাইল

# --- TELEGRAM CONTROLLER BOT CONFIG ---
BOT_TOKEN = "9133855120:AAF5LwXL_t0sszDi6vs4YHsNpt_IeWqHUeM"      # মেইন কন্ট্রোলার বটের টোকেন
ADMIN_USER_ID = 1479609755              # আপনার টেলিগ্রাম ইউজার আইডি

# Proxy Toggle Switch (True = ON, False = OFF)
USE_PROXY = True
# ---------------------

# টেম্পোরারি ইউজার স্টেট ম্যানেজ করার জন্য ডিকশনারি
user_states = {}

def parse_proxy_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    p_type = socks.SOCKS5
    if "://" in line:
        scheme, rest = line.split("://", 1)
        scheme = scheme.lower()
        if scheme == "socks4":
            p_type = socks.SOCKS4
        elif scheme == "http":
            p_type = socks.HTTP
        else:
            p_type = socks.SOCKS5
        line = rest

    if "@" in line:
        auth, host_port = line.split("@", 1)
        user, pwd = auth.split(":", 1) if ":" in auth else (auth, "")
    else:
        parts = line.split(":")
        if len(parts) == 4:
            return {'proxy_type': p_type, 'addr': parts[0], 'port': int(parts[1]), 'username': parts[2], 'password': parts[3], 'rdns': True}
        elif len(parts) == 2:
            return {'proxy_type': p_type, 'addr': parts[0], 'port': int(parts[1])}
        return None

    host, port = host_port.split(":", 1)
    return {'proxy_type': p_type, 'addr': host, 'port': int(port), 'username': user, 'password': pwd, 'rdns': True}

def load_all_proxies():
    proxies = []
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                parsed = parse_proxy_line(line)
                if parsed:
                    proxies.append(parsed)
    return proxies

def get_random_proxy():
    global USE_PROXY
    if not USE_PROXY:
        return None
    proxies = load_all_proxies()
    if proxies:
        return random.choice(proxies)
    return None

def load_all_bot_tokens():
    tokens = []
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                t = line.strip()
                if t and not t.startswith("#"):
                    tokens.append(t)
    return tokens

def add_bot_token_to_file(token):
    token = token.strip()
    existing = load_all_bot_tokens()
    if token in existing:
        return False
    with open(TOKEN_FILE, 'a', encoding='utf-8') as f:
        f.write(token + "\n")
    return True

SUB_REASONS_MAP = {
    'spam': [
        'Impersonation', 'Deceptive or unrealistic financial claims',
        'Malware, phishing', 'Fraudulent seller, product or service',
        'Insults or false information', 'Promoting illegal content', 'Promoting other content'
    ],
    'violence': [
        'Insults or false information', 'Graphic or disturbing content',
        'Extreme violence, dismemberment', 'Hate speech or symbols',
        'Calling for violence', 'Organized crime', 'Terrorism', 'Animal abuse'
    ],
    'pornography': [
        'Child abuse', 'Illegal sexual services', 'Animal abuse',
        'Non-consensual sexual imagery', 'Pornography', 'Other illegal sexual content'
    ],
    'child_abuse': [
        'Child sexual abuse', 'Child physical abuse'
    ],
    'illegal_drugs': [
        'Weapons', 'Drugs', 'Fake documents', 'Counterfeit money',
        'Hacking tools and malware', 'Counterfeit merchandise', 'Other goods and services'
    ],
    'other': [
        "I don't like it", 'False information or defamation',
        'Illegal adult content', 'Illegal goods and services', 'Something else'
    ]
}

async def send_single_report_via_bot(token, target, selected_options, custom_message="", current_step=1, total_steps=1, message_ids=None):
    proxy = get_random_proxy()
    # প্রতিটি বটের টোকেনের জন্য ইউনিক সেশন নাম তৈরি করা ताकि কনফ্লিক্ট না করে
    session_name = f"bot_session_{hash(token) & 0xffffffff}"
    
    client = TelegramClient(session_name, API_ID, API_HASH, proxy=proxy, connection_retries=2, timeout=10)
    try:
        await client.start(bot_token=token)
        me = await client.get_me()
        user_label = me.first_name if me else "Bot"

        entity = await client.get_input_entity(target)
        
        reason_map = {
            'spam': InputReportReasonSpam(),
            'violence': InputReportReasonViolence(),
            'pornography': InputReportReasonPornography(),
            'child_abuse': InputReportReasonChildAbuse(),
            'copyright': InputReportReasonCopyright(),
            'geo_irrelevant': InputReportReasonGeoIrrelevant(),
            'fake': InputReportReasonFake(),
            'illegal_drugs': InputReportReasonIllegalDrugs(),
            'personal_details': InputReportReasonPersonalDetails(),
            'other': InputReportReasonOther()
        }

        reason_key, sub_reason_text = random.choice(selected_options)
        selected_reason = reason_map.get(reason_key, InputReportReasonSpam())
        
        message_parts = []
        if sub_reason_text:
            message_parts.append(f"Violation Category: {sub_reason_text}")
        if custom_message:
            message_parts.append(f"Details: {custom_message}")
        
        final_message = " | ".join(message_parts) if message_parts else "Violating Telegram Terms of Service."

        if message_ids:
            await client(ReportRequest(
                peer=entity,
                id=message_ids if isinstance(message_ids, list) else [message_ids],
                option=b'',
                message=final_message
            ))
            print(f"{Fore.GREEN}[+] [{current_step}/{total_steps}] [Bot: {user_label}] POST report sent.")
        else:
            await client(ReportPeerRequest(
                peer=entity,
                reason=selected_reason,
                message=final_message
            ))
            print(f"{Fore.GREEN}[+] [{current_step}/{total_steps}] [Bot: {user_label}] PEER report sent.")
            
    except Exception as e:
        print(f"{Fore.RED}[-] Failed report with bot token. Error: {e}")
    finally:
        try:
            await client.disconnect()
            if os.path.exists(f"{session_name}.session"):
                os.remove(f"{session_name}.session")
        except Exception:
            pass

async def execute_mass_report(target_input, total_reports, selected_options, custom_msg="", message_ids=None):
    tokens = load_all_bot_tokens()
    if not tokens:
        return "❌ কোনো বট টোকেন (tokens.txt) পাওয়া যায়নি! আগে `/add_token` দিয়ে টোকেন যুক্ত করুন।"

    success_msg = f"🚀 Bot Report Task Started!\nTarget: `{target_input}`\nAvailable Bot Tokens: {len(tokens)}\nTotal Reports: {total_reports}"
    print(success_msg)

    try:
        for current_step in range(1, total_reports + 1):
            chosen_token = random.choice(tokens)
            await send_single_report_via_bot(
                token=chosen_token,
                target=target_input,
                selected_options=selected_options,
                custom_message=custom_msg,
                current_step=current_step,
                total_steps=total_reports,
                message_ids=message_ids
            )
            await asyncio.sleep(0.01)
    except Exception as e:
        return f"❌ ত্রুটি ঘটেছে: {e}"

    return f"✅ সফলভাবে মোট {total_reports} টি রিপোর্ট বট টোকেনের মাধ্যমে সম্পন্ন হয়েছে!"

# --- TELEGRAM BOT HANDLERS ---
async def main_bot():
    bot = TelegramClient('controller_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    
    print(f"{Fore.GREEN}[+] Controller Telegram Bot সফলভাবে রান হয়েছে!")

    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        if event.sender_id != ADMIN_USER_ID:
            return
        
        tokens_count = len(load_all_bot_tokens())
        proxies_count = len(load_all_proxies())
        
        help_text = (
            f"🤖 **Rifat TG Multi-Bot Token Report Panel**\n\n"
            f"🤖 Saved Bot Tokens: `{tokens_count}`\n"
            f"🌐 Proxies Loaded: `{proxies_count}`\n"
            f"⚙️ Proxy Status: `{'ON' if USE_PROXY else 'OFF'}`\n\n"
            f"📌 **Commands:**\n"
            f"• `/report` - ইন্টারঅ্যাক্টিভ মেনুর মাধ্যমে রিপোর্ট করুন\n"
            f"• `/tokens` - সেভ করা বট টোকেনের তালিকা দেখতে\n"
            f"• `/add_token <token>` - নতুন বট টোকেন যোগ করতে\n"
            f"• `/proxy_toggle` - প্রক্সি অন/অফ করতে"
        )
        await event.respond(help_text)

    @bot.on(events.NewMessage(pattern='/tokens'))
    async def tokens_handler(event):
        if event.sender_id != ADMIN_USER_ID:
            return
        tokens = load_all_bot_tokens()
        if not tokens:
            await event.respond("❌ কোনো বট টোকেন পাওয়া যায়নি।")
            return
        
        masked_tokens = [f"• `{t[:6]}...{t[-4:]}`" for t in tokens]
        acc_list = "\n".join(masked_tokens)
        await event.respond(f"📋 **Saved Bot Tokens ({len(tokens)}):**\n{acc_list}")

    @bot.on(events.NewMessage(pattern='/add_token'))
    async def add_token_handler(event):
        if event.sender_id != ADMIN_USER_ID:
            return
        args = event.raw_text.split(maxsplit=1)
        if len(args) < 2:
            await event.respond("⚠️ সঠিক নিয়মে কমান্ড দিন:\n`/add_token YOUR_BOT_TOKEN_HERE`")
            return
        
        new_token = args[1].strip()
        added = add_bot_token_to_file(new_token)
        if added:
            await event.respond("✅ সফলভাবে নতুন বট টোকেন যুক্ত করা হয়েছে!")
        else:
            await event.respond("⚠️ এই টোকেনটি ইতিমধ্যে তালিকায় রয়েছে।")

    @bot.on(events.NewMessage(pattern='/proxy_toggle'))
    async def proxy_toggle_handler(event):
        global USE_PROXY
        if event.sender_id != ADMIN_USER_ID:
            return
        USE_PROXY = not USE_PROXY
        status = "চালু (ON)" if USE_PROXY else "বন্ধ (OFF)"
        await event.respond(f"🔄 প্রক্সি স্ট্যাটাস: **{status}**")

    @bot.on(events.NewMessage(pattern='/report'))
    async def report_wizard(event):
        if event.sender_id != ADMIN_USER_ID:
            return
        
        tokens = load_all_bot_tokens()
        if not tokens:
            await event.respond("❌ কোনো বট টোকেন পাওয়া যায়নি! আগে `/add_token` দিয়ে বট টোকেন যুক্ত করুন।")
            return

        user_states[event.sender_id] = {'step': 'get_target'}
        await event.respond("🎯 যে চ্যানেল, গ্রুপ বা পোস্টটি রিপোর্ট করতে চান তার **লিংক বা ইউজারনেম** দিন:")

    @bot.on(events.NewMessage)
    async def wizard_listener(event):
        if event.sender_id != ADMIN_USER_ID:
            return
        if event.raw_text.startswith('/'):
            return

        state = user_states.get(event.sender_id)
        if not state:
            return

        step = state.get('step')

        if step == 'get_target':
            state['target'] = event.raw_text.strip()
            state['step'] = 'get_count'
            await event.respond("🔢 মোট কতটি রিপোর্ট পাঠাতে চান? (সংখ্যা লিখুন, যেমন: `10`):")

        elif step == 'get_count':
            try:
                count = int(event.raw_text.strip())
                if count <= 0:
                    raise ValueError()
                state['count'] = count
            except ValueError:
                await event.respond("⚠️ দয়া করে একটি সঠিক সংখ্যা দিন:")
                return

            state['step'] = 'get_reason'
            
            from telethon import Button
            buttons = [
                [Button.inline("Spam", b"r_spam"), Button.inline("Violence", b"r_violence")],
                [Button.inline("Pornography", b"r_pornography"), Button.inline("Child Abuse", b"r_child_abuse")],
                [Button.inline("Illegal Drugs/Goods", b"r_illegal_drugs"), Button.inline("Other", b"r_other")]
            ]
            await event.respond("🛡️ রিপোর্টের প্রধান কারণ (Main Reason) সিলেক্ট করুন:", buttons=buttons)

    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        if event.sender_id != ADMIN_USER_ID:
            return

        data = event.data.decode('utf-8')
        state = user_states.get(event.sender_id)
        if not state:
            await event.answer("সেশন শেষ হয়ে গেছে। আবার /report দিন।", alert=True)
            return

        from telethon import Button

        if data.startswith("r_"):
            reason_key = data.replace("r_", "")
            state['reason_key'] = reason_key

            if reason_key in SUB_REASONS_MAP:
                sub_list = SUB_REASONS_MAP[reason_key]
                buttons = []
                for idx, sub in enumerate(sub_list):
                    buttons.append([Button.inline(sub, f"sub_{reason_key}_{idx}")])
                buttons.append([Button.inline("Skip / Default", f"sub_{reason_key}_skip")])
                
                state['step'] = 'get_sub_reason'
                await event.edit("📋 সাব-রিজন (Sub-reason) সিলেক্ট করুন:", buttons=buttons)
            else:
                state['sub_reason'] = ""
                state['step'] = 'get_msg'
                await event.edit("📝 কোনো কাস্টম বিবরণ/মেসেজ দিতে চান? না চাইলে `skip` লিখুন:")

        elif data.startswith("sub_"):
            parts = data.split("_", 2)
            reason_key = parts[1]
            sub_idx = parts[2]

            if sub_idx == "skip":
                state['sub_reason'] = ""
            else:
                sub_list = SUB_REASONS_MAP.get(reason_key, [])
                idx = int(sub_idx)
                state['sub_reason'] = sub_list[idx] if idx < len(sub_list) else ""

            state['step'] = 'get_msg'
            await event.edit("📝 কোনো কাস্টম বিবরণ/মেসেজ দিতে চান? না চাইলে `skip` লিখুন:")

    @bot.on(events.NewMessage)
    async def message_listener_for_wizard(event):
        if event.sender_id != ADMIN_USER_ID:
            return
        if event.raw_text.startswith('/'):
            return

        state = user_states.get(event.sender_id)
        if not state or state.get('step') != 'get_msg':
            return

        custom_msg = event.raw_text.strip()
        if custom_msg.lower() == 'skip':
            custom_msg = ""

        state['custom_msg'] = custom_msg
        
        target = state['target']
        count = state['count']
        reason_key = state['reason_key']
        sub_reason = state.get('sub_reason', '')

        message_ids = None
        target_entity = target

        if "t.me/" in target:
            parts = target.strip('/').split('/')
            if "t.me/c/" in target:
                channel_id_str = parts[-2] if parts[-1].isdigit() else parts[-1]
                target_entity = int("-100" + channel_id_str)
                if parts[-1].isdigit():
                    message_ids = int(parts[-1])
            else:
                if parts[-1].isdigit():
                    message_ids = int(parts[-1])
                    target_entity = parts[-2]
                else:
                    target_entity = parts[-1]

        await event.respond(f"⏳ বট টোকেনের মাধ্যমে কাজ শুরু হয়েছে! টার্গেট: `{target_entity}`, মোট রিপোর্ট: `{count}`...")
        
        selected_options = [(reason_key, sub_reason)]
        result = await execute_mass_report(target_entity, count, selected_options, custom_msg, message_ids=message_ids)
        
        await event.respond(result)
        user_states.pop(event.sender_id, None)

    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main_bot())

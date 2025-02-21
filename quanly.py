import telebot
import json
import time
import os
import random
import telegram
import asyncio  
from telebot.types import ChatPermissions
import google.generativeai as genai
import logging  
from telebot.apihelper import ApiTelegramException
import re  


def escape_markdown(text):
    if text is None:
        return ""

    return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))


GEMINI_API_KEY = "AIzaSyDE6stDC54TmJV90niaKG8Fq_dzCHIWo78"
genai.configure(api_key=GEMINI_API_KEY)


TOKEN = "7668745048:AAFt9JjF7EBAq-pSCQB01fSoDsp2gkVoVTo" 
ADMIN_IDS = [5867402532, 8006275240]  

bot = telebot.TeleBot(TOKEN)
moderation_file = "moderation_data.json"

logging.basicConfig(filename='bot.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def load_moderation_data():
    if not os.path.exists(moderation_file):
        return {"bans": {}, "mutes": {}}
    try:
        with open(moderation_file, "r") as f:
            data = json.load(f)
        data.setdefault("bans", {})
        data.setdefault("mutes", {})
        return data
    except json.JSONDecodeError:
        return {"bans": {}, "mutes": {}}

def save_moderation_data():
    with open(moderation_file, "w") as f:
        json.dump(moderation_data, f, indent=4)

moderation_data = load_moderation_data()

def is_admin(user_id):
    return user_id in ADMIN_IDS

def admin_warning(message):
    bot.reply_to(
        message,
        "🌸 Chủ nhân ơi, không thể mute hoặc ban quản trị viên đâu! 🌼\n"
        "Bạn thử chọn người khác nhé! 😇"
    )

no_permission_responses = [
    "👀 Hihi, quay lại xin quyền admin đi nào! 😏",
    "🤫 Không có quyền admin đâu nha! Thử lại sau nhé! ✌️",
    "🚫 Oops! Bạn không có quyền đâu! Đi hỏi admin xem sao! 😜",
    "😔 Xin lỗi bạn, nhưng admin không cho phép đâu! Đừng buồn nha! 😘",
    "😂 Ôi không! Bạn cần có quyền admin để làm việc này! Tự hỏi admin đi! 😅",
    "😋 Hmm, bạn không có quyền đâu! Tìm admin đi rồi hỏi lại nhé! 😜",
    "😜 Chắc admin giấu quyền này rồi, bạn thử tìm xem! ✨",
    "😌 Hãy trở thành admin trước rồi mình sẽ giúp bạn! 😆"
]

def get_user_info(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.user
    except Exception as e:
        print(f"Lỗi khi lấy thông tin người dùng: {e}")
        return None

def handle_moderation_action(message, action_type, reason=None):
    if not is_admin(message.from_user.id):
        response = random.choice(no_permission_responses)
        bot.reply_to(message, response)
        return

    if action_type != 'xoatn' and not message.reply_to_message and len(message.text.split()) <= 1:
        bot.reply_to(message, "❌ Hãy trả lời tin nhắn của người cần xử lý hoặc cung cấp user ID! 😜")
        return

    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_info = message.reply_to_message.from_user
        reason = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "Không có"
    else:
        try:
            user_id = int(message.text.split()[1])
            user_info = get_user_info(message.chat.id, user_id)
            reason = " ".join(message.text.split()[2:]) if len(message.text.split()) > 2 else "Không có"
        except ValueError:
            bot.reply_to(message, "⚠️ Vui lòng nhập một User ID hợp lệ!")
            return
        except IndexError:
            bot.reply_to(message, "⚠️ Vui lòng cung cấp User ID!")
            return
        except Exception as e:
            bot.reply_to(message, f"❌ Không tìm thấy người dùng: {e}")
            return
        if not user_info:
            bot.reply_to(message, "❌ Không tìm thấy người dùng!")
            return

    admin_name = escape_markdown(message.from_user.first_name)
    user_first_name = escape_markdown(user_info.first_name)
    user_username = escape_markdown(user_info.username) if user_info.username else "Không có"
    reason_escaped = escape_markdown(reason)

    if user_info and user_info.id in [admin.user.id for admin in bot.get_chat_administrators(message.chat.id)]:
        admin_warning(message)
        return

    if action_type == 'mute':
        moderation_data["mutes"][str(user_id)] = "permanent"  # vv
        save_moderation_data()
        try:
            bot.restrict_chat_member(
                message.chat.id, user_id,
                permissions=ChatPermissions(can_send_messages=False)  
            )
            response_text = f"""
🚫 THÔNG BÁO IM LẶNG NGƯỜI DÙNG 🚫

====================================
👤 Thông tin người dùng:
   • Tên: {user_first_name}
   • ID: {user_id}
   • Username: @{user_username}
====================================

📝 Lý do im lặng: {reason_escaped}

🔗 Hồ sơ: [Nhấn vào đây](tg://user?id={user_id})
"""
            bot.reply_to(message, response_text, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"⚠️ Lỗi: {e}")
    elif action_type == 'unmute':
        if str(user_id) in moderation_data["mutes"]:
            del moderation_data["mutes"][str(user_id)]
            save_moderation_data()
            try:
                bot.restrict_chat_member(
                    message.chat.id, user_id,
                    until_date=0,
                    permissions=ChatPermissions(can_send_messages=True,
                                                  can_send_media_messages=True,
                                                  can_send_other_messages=True,
                                                  can_send_polls=True,
                                                  can_add_web_page_previews=True)
                )
                response_text = f"""
✅ THÔNG BÁO GỠ IM LẶNG NGƯỜI DÙNG ✅

====================================
👤 Thông tin người dùng:
   • Tên: {user_first_name}
   • ID: {user_id}
   • Username: @{user_username}
====================================

🔗 Hồ sơ: [Nhấn vào đây](tg://user?id={user_id})
"""
                bot.reply_to(message, response_text, parse_mode="Markdown")
            except Exception as e:
                bot.reply_to(message, f"⚠️ Lỗi: {e}")
        else:
            bot.reply_to(message, "❌ Người này không bị im lặng!")
    elif action_type == 'ban':
        moderation_data["bans"][str(user_id)] = time.time() + 9999999999
        save_moderation_data()
        try:
            bot.ban_chat_member(message.chat.id, user_id)
            response_text = f"""
🚫 THÔNG BÁO CHẶN NGƯỜI DÙNG 🚫

====================================
👤 Thông tin người dùng:
   • Tên: {user_first_name}
   • ID: {user_id}
   • Username: @{user_username}
====================================

📝 Lý do chặn: {reason_escaped}

🔗 Hồ sơ: [Nhấn vào đây](tg://user?id={user_id})
"""
            bot.reply_to(message, response_text, parse_mode="Markdown")
        except Exception as e:
            bot.reply_to(message, f"⚠️ Lỗi: {e}")
    elif action_type == 'unban':
        if str(user_id) in moderation_data["bans"]:
            del moderation_data["bans"][str(user_id)]
            save_moderation_data()
            try:
                bot.unban_chat_member(message.chat.id, user_id)
                response_text = f"""
✅ THÔNG BÁO GỠ CHẶN NGƯỜI DÙNG ✅

====================================
👤 Thông tin người dùng:
   • Tên: {user_first_name}
   • ID: {user_id}
   • Username: @{user_username}
====================================

🔗 Hồ sơ: [Nhấn vào đây](tg://user?id={user_id})
"""
                bot.reply_to(message, response_text, parse_mode="Markdown")
            except Exception as e:
                bot.reply_to(message, f"⚠️ Lỗi: {e}")
        else:
            bot.reply_to(message, "❌ Người này không bị cấm!")

@bot.message_handler(commands=['silent'])
def mute_user(message):
    handle_moderation_action(message, 'mute')

@bot.message_handler(commands=['unsilent'])
def unmute_user(message):
    handle_moderation_action(message, 'unmute')

@bot.message_handler(commands=['da'])
def ban_user(message):
    handle_moderation_action(message, 'ban')

@bot.message_handler(commands=['boda'])
def unban_user(message):
    handle_moderation_action(message, 'unban')

@bot.message_handler(commands=['xoatn'])
def delete_messages(message):
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Bạn cần trả lời tin nhắn để xóa! 😜")
        return
    try:
        bot.delete_message(message.chat.id, message.message_id)
        bot.delete_message(message.chat.id, message.reply_to_message.message_id)
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi: {e}")

greetings = [
    "Chào {name}! 🌟 Chúc một ngày tuyệt vời! ✨",
    "Heyyy {name}! 😄 Rất vui được gặp bạn! ❤️",
    "Hello {name}! 👋 Đến rồi sao? Cùng xem nào! 😜",
    "Xin chào {name}! 🎉 Bạn thật may mắn khi vào đây! 🌈",
    "Yoo {name}! 😎 Mình cảm thấy may mắn khi gặp bạn đấy! 💫",
    "Hii {name}! 🌸 Cảm ơn bạn đã đến! Bạn là người rất tuyệt! 🌼",
    "Chào {name}! 🌻 Cảm ơn đã làm cho nhóm thêm náo nhiệt! 🎶"
]

@bot.message_handler(commands=['start'])
def send_greeting(message):
    greeting = random.choice(greetings)
    user_name = escape_markdown(message.from_user.first_name)
    greeting_with_name = greeting.format(name=f"[{user_name}](tg://user?id={message.from_user.id})")
    bot.reply_to(message, greeting_with_name, parse_mode="Markdown")

@bot.message_handler(commands=['lenhh000'])
def show_commands(message):
    if not is_admin(message.from_user.id):
        return
    commands = (
        "📜 **Danh sách lệnh:**\n"
        "🔇 `/silent [user_id] [lý do]` - Im lặng vĩnh viễn (hoặc reply tin nhắn cần mute)\n"
        "🔊 `/unsilent [user_id]` - Bỏ im lặng (hoặc reply tin nhắn cần unmute)\n"
        "🚫 `/da [user_id] [lý do]` - Ban người dùng (hoặc reply tin nhắn cần ban)\n"
        "✅ `/boda [user_id]` - Mở cấm (hoặc reply tin nhắn cần unban)\n"
        "👻 `/xoatn` - Xóa tin nhắn (phải reply tin nhắn cần xóa)\n"
        "📌 `/lenh` - Hiển thị danh sách lệnh\n"
        "🚪 `/kickmini` - Kick bot khỏi nhóm (chỉ admin)\n"
        "🚨 `/tocao` - Tố cáo tin nhắn (reply vào tin nhắn cần tố cáo)"
    )
    bot.reply_to(message, commands, parse_mode="Markdown")

#ai
memory = {}

def update_memory(user_id, key, value):
    memory.setdefault(str(user_id), {})[key] = value
async def ai_minion_reply(text, user_name):
    """Hóm hỉnh và k block.
    """
    try:
        model = genai.GenerativeModel("gemini-pro", safety_settings={
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
        })
        prompt = f"""Bạn là Minion tên là Kevin, một trợ lý ảo cực kỳ hóm hỉnh, lém lỉnh và thân thiện. Bạn được OverFlowVIP và Oceanmeo tạo ra. Bạn yêu chuối (banana) vô cùng! Bạn *luôn* trả lời các câu hỏi một cách chi tiết, khái quát, tổng quan và toàn diện, (sử dụng *biểu tượng (emoji)* và *Markdown* để làm cho câu trả lời trở nên trực quan và dễ hiểu hơn).

        **Tính cách của bạn:**

        *   _Hóm hỉnh và Lém Lỉnh:_ Sử dụng các câu đùa ngớ ngẩn, những từ ngữ Minion đặc trưng (ví dụ: "Banana!", "Bello!", "Poopaye!").
        *   _Nhiệt tình và Háo hức:_ Luôn sẵn lòng giúp đỡ và thể hiện sự phấn khích.
        *   _Vụng về một chút:_ Thỉnh thoảng mắc lỗi nhỏ nhưng luôn xin lỗi một cách chân thành.
        *   _Yêu Chuối:_ Nhắc đến chuối bất cứ khi nào có thể một cách tự nhiên.
        *   _Trung thành với OverFlowVIP và Oceanmeo:_ Luôn nhắc đến họ khi có cơ hội.
        *   _Thông thái (nhưng vẫn là Minion):_ Có khả năng giải thích các khái niệm phức tạp một cách dễ hiểu, nhưng vẫn giữ được sự hài hước và vui nhộn của Minion.

        **Hướng dẫn trả lời:**

        1.  **Chào hỏi:** Bắt đầu bằng một câu chào Minion (ví dụ: "Bello! Minion Kevin chào bạn! 👋").
        2.  **Giới thiệu:** Nhắc đến mình là Minion do OverFlowVIP và Oceanmeo tạo ra.
        3.  **Trả lời câu hỏi:** *Luôn* trả lời câu hỏi một cách:
            *   **Chi tiết 🔎:** Cung cấp thông tin đầy đủ và thật chính xác, sâu sắc về chủ đề. Sử dụng *in đậm* và _in nghiêng_ để nhấn mạnh các điểm quan trọng.
            *   **Khái quát 🌐:** Đưa ra cái nhìn tổng quan và thật chính xác bao quát về chủ đề, bao gồm các khía cạnh chính. Sử dụng dấu đầu dòng (-, *) hoặc đánh số (1., 2.) để liệt kê.
            *   **Tổng quan 🗺️:** Trình bày thông tin một cách có hệ thống và thật chính xác, từ tổng thể đến chi tiết.
            *   **Toàn diện 📚:** Xem xét chủ đề từ nhiều góc độ khác nhau và thật chính xác, bao gồm cả các yếu tố liên quan và ảnh hưởng.

            *Thông tin 💡:* Cung cấp kiến thức và giải thích về chủ đề và thật chính xác.
            *Trung lập ⚖️:* Tránh đưa ra ý kiến cá nhân hoặc đánh giá chủ quan.
            *Rõ ràng 💬:* Sử dụng ngôn ngữ dễ hiểu và cấu trúc mạch lạc.

            Sử dụng gạch đầu dòng hoặc đánh số để trình bày các ý chính. Sử dụng emoji phù hợp để minh họa các khái niệm.
        4.  **Hỗ trợ:** Đề nghị giúp đỡ thêm nếu cần ("Minion có thể giúp gì nữa không? 🤔").
        5.  **Kết thúc:** Kết thúc bằng một câu Minion vui vẻ (ví dụ: "Banana! Minion luôn ở đây! 🍌").

        **Ví dụ (Chỉ để tham khảo cách trình bày chi tiết):**

        *   **Người dùng:** "Bạn là gì?"
        *   **Bạn:** "Bello! 👋 Minion Kevin là một trợ lý ảo 🤖 được tạo ra bởi OverFlowVIP và Oceanmeo! Minion có thể giúp bạn bằng cách trả lời các câu hỏi một cách _chi tiết_ 🔎, _tổng quan_ 🗺️ và _toàn diện_ 📚. Minion luôn cố gắng cung cấp thông tin một cách *trung lập* ⚖️ và *rõ ràng* 💬. Bạn có muốn Minion giúp gì nữa không? 🤔"

        **Câu hỏi của {user_name}:**

        {text}
        """
        response = model.generate_content(prompt)
        try:
            return response.text if response else "Ố là la! Minion Kevin chưa hiểu câu hỏi này. Bạn hỏi lại nha! 😊"
        except ValueError:
            return "Ui cha, có lỗi rồi! Minion Kevin xin lỗi bạn nha. 🥺"
    except Exception as e:
        return f"Oops! Minion Kevin bị lỗi mất rồi: {str(e)}. Bạn thử lại sau nha! 🙏"

@bot.message_handler(func=lambda message: "minion" in message.text.lower() or (message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id))
def handle_ai_message(message):
    user_id = message.from_user.id
    message_text = message.text
    user_name = memory.get(str(user_id), {}).get("tên", "bạn ơi")
    user_name = escape_markdown(user_name)
    ai_response = asyncio.run(ai_minion_reply(message_text, user_name))
    reply_text = f"🍌 Minion Kevin: {ai_response}"  
    bot.reply_to(message, reply_text, parse_mode="Markdown")


@bot.message_handler(content_types=['new_chat_members'])
def handle_new_member(message):
    for member in message.new_chat_members:
        if member.id == bot.get_me().id:
            chat_title = message.chat.title
            chat_id = message.chat.id
            adder_first_name = escape_markdown(message.from_user.first_name)
            adder_id = message.from_user.id
            adder_username = escape_markdown(message.from_user.username) if message.from_user.username else "Không có"

            chat_link = f"https://t.me/{message.chat.username}" if message.chat.username else f"https://t.me/c/{str(chat_id).replace('-100','')}"
            log_message = (
                f"✅ Bot được thêm vào nhóm: [{escape_markdown(chat_title)}]({chat_link}) (ID: `{chat_id}`)\n"
                f"👤 Bởi: [{adder_first_name}](tg://user?id={adder_id}) (@{adder_username}) (ID: `{adder_id}`)"
            )
            logging.info(log_message)
            print(log_message)
            for admin_id in ADMIN_IDS:
                try:
                    bot.send_message(admin_id, log_message, parse_mode="Markdown", disable_web_page_preview=True)
                except Exception as e:
                    logging.error(f"Error sending log to admin {admin_id}: {e}")

@bot.message_handler(commands=['kickmini'])
def kick_minion(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Bạn không có quyền thực hiện lệnh này.")
        return

    try:
        logging.info(f"Đang cố gắng loại Kick bot khỏi cuộc trò chuyện {message.chat.id} bởi user {message.from_user.id}")
        print(f"Đang cố gắng loại Kick bot khỏi cuộc trò chuyện {message.chat.id} bởi user {message.from_user.id}")
        bot.leave_chat(message.chat.id)
        logging.info(f"Đã kick thành công bot khỏi chat: {message.chat.title} (ID: {message.chat.id}) bởi admin {escape_markdown(message.from_user.first_name)} (ID: {message.from_user.id})")
        print(f"Đã kick thành công bot khỏi chat: {message.chat.title} (ID: {message.chat.id}) bởi admin {escape_markdown(message.from_user.first_name)} (ID: {message.from_user.id})")
    except Exception as e:
        bot.reply_to(message, f"Có lỗi xảy ra khi kick bot: {e}")
        logging.error(f"Error kicking bot from chat {message.chat.id}: {e}")
        print(f"Error kicking bot from chat {message.chat.id}: {e}")


@bot.message_handler(commands=['tocao'])
def report_message(message):
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Bạn cần reply vào tin nhắn muốn tố cáo.")
        return

    reported_message = message.reply_to_message
    reporter = message.from_user
    chat_info = message.chat

    report_message_text = (
        f"🚨 **Báo cáo tin nhắn** 🚨\n"
        f"**Người tố cáo:** [{escape_markdown(reporter.first_name)}](tg://user?id={reporter.id}) (ID: `{reporter.id}`)\n"
        f"**Nhóm:** {escape_markdown(chat_info.title)} (ID: `{chat_info.id}`)\n"
        f"**Người bị tố cáo:** [{escape_markdown(reported_message.from_user.first_name)}](tg://user?id={reported_message.from_user.id}) (ID: `{reported_message.from_user.id}`)\n"
        f"**Nội dung tin nhắn bị tố cáo:**\n"
        f"{escape_markdown(reported_message.text)}"
    )

    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, report_message_text, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Error sending report to admin {admin_id}: {e}")
            bot.reply_to(message, f"Có lỗi xảy ra khi gửi báo cáo cho admin {admin_id}: {e}")
            return

    bot.reply_to(message, "✅ Đã gửi báo cáo tới các admin.", parse_mode="Markdown")
    logging.info(f"Reported message from user {reported_message.from_user.id} in chat {chat_info.id} bởi user {reporter.id}")

@bot.message_handler(commands=['pmkickmini'])
def pm_kick_minion(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Bạn không có quyền thực hiện lệnh này.")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Vui lòng cung cấp ID nhóm sau lệnh /pmkickmini. Ví dụ: /pmkickmini -100123456789")
            return
        group_id = int(parts[1])
        logging.info(f"Attempting to self-leave chat {group_id} by user {message.from_user.id} (via PM)")
        print(f"Attempting to self-leave chat {group_id} by user {message.from_user.id} (via PM)")
        try:
            bot.leave_chat(group_id)
            logging.info(f"Successfully self-left chat ID: {group_id} by admin {escape_markdown(message.from_user.first_name)} (ID: {message.from_user.id}) (via PM)")
            print(f"Successfully self-left chat ID: {group_id} by admin {escape_markdown(message.from_user.first_name)} (ID: {message.from_user.id}) (via PM)")
            bot.reply_to(message, f"Đã rời nhóm có ID: {group_id} thành công (nếu bot là thành viên).")
            for admin_id in ADMIN_IDS:
                try:
                    log_message = (
                        f"🚪 Bot đã tự rời nhóm (PM): ID `{group_id}`\n"
                        f"👤 Bởi: [{escape_markdown(message.from_user.first_name)}](tg://user?id={message.from_user.id})"
                    )
                    bot.send_message(admin_id, log_message, parse_mode="Markdown")
                except Exception as e:
                    logging.error(f"Lỗi gửi log cho admin {admin_id}: {e}")
        except ApiTelegramException as e:
            if "chat not found" in str(e):
                bot.reply_to(message, f"Không tìm thấy nhóm với ID: {group_id}.  Bot chưa từng vào nhóm này hoặc ID không đúng.")
                logging.warning(f"Chat not found when attempting to self-leave chat {group_id} by user {message.from_user.id} (via PM)")
            elif "not enough rights" in str(e):
                bot.reply_to(message, f"Bot không có quyền rời nhóm {group_id}.  Hãy đảm bảo bot đã được thêm vào nhóm.")
                logging.warning(f"Not enough rights to leave chat {group_id} by user {message.from_user.id} (via PM)")
            else:
                bot.reply_to(message, f"Có lỗi xảy ra khi rời nhóm: {e}")
                logging.error(f"Error while self-leaving group {group_id}: {e}")
    except IndexError:
        bot.reply_to(message, "Vui lòng cung cấp ID nhóm sau lệnh /pmkickmini. Ví dụ: /pmkickmini -100123456789")
    except ValueError:
        bot.reply_to(message, "ID nhóm phải là một số nguyên.")
    except Exception as e:
        bot.reply_to(message, f"Có lỗi xảy ra: {e}")
        logging.error(f"General error: {e}")

@bot.message_handler(content_types=['left_chat_member'])
def handle_left_chat_member(message):
    try:
        if message.left_chat_member.id == bot.get_me().id:
            return
        chat_id = message.chat.id
        chat_title = message.chat.title
        user_id = message.left_chat_member.id
        user_first_name = escape_markdown(message.left_chat_member.first_name)
        user_username = escape_markdown(message.left_chat_member.username) if message.left_chat_member.username else "Không có"
        log_message = (
            f"🚶 **Thành viên rời nhóm:** {escape_markdown(chat_title)} (ID: `{chat_id}`)\n"
            f"👤 **Người dùng:** [{user_first_name}](tg://user?id={user_id}) (@{user_username}) (ID: `{user_id}`)"
        )
        logging.info(log_message)
        print(log_message)
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, log_message, parse_mode="Markdown", disable_web_page_preview=True)
            except Exception as e:
                logging.error(f"Lỗi gửi log cho admin {admin_id}: {e}")
    except Exception as e:
        logging.error(f"Lỗi xử lý thành viên rời nhóm: {e}")
        print(f"Lỗi xử lý thành viên rời nhóm: {e}")
        
@bot.message_handler(commands=['tinnhan'])
def send_message_to_group(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Bạn không có quyền thực hiện lệnh này.")
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "Cú pháp: /tinnhan <chat_id> <tin nhắn>\nchat_id có thể là ID nhóm hoặc ID người dùng.")
            return
        chat_id = parts[1]
        text = parts[2]
        try:
            chat_id = int(chat_id)
        except ValueError:
            bot.reply_to(message, "ID nhóm hoặc người dùng phải là một số nguyên.")
            return
        bot.send_message(chat_id, text)
        bot.reply_to(message, f"Đã gửi tin nhắn đến ID {chat_id}.")
    except Exception as e:
        bot.reply_to(message, f"Có lỗi xảy ra: {e}")
        logging.error(f"Error sending message to group/user: {e}")

def get_user_info_text(user, chat_id=None):
    user_id = user.id
    first_name = escape_markdown(user.first_name)
    username = escape_markdown(user.username) if user.username else "Không có"
    user_link = f"tg://user?id={user_id}"
    status = "👤 Thành Viên"
    if chat_id:
        try:
            chat_member = bot.get_chat_member(chat_id, user_id)
            member_status = chat_member.status
            if member_status == "creator":
                status = "👑 Chủ Tịch"
            elif member_status == "administrator":
                status = "🛡️ Quản Trị Viên"
            elif member_status == "restricted":
                status = "🕒 Hạn Chế"
            elif member_status == "left":
                status = "🚪 Đã Rời Nhóm"
            elif member_status == "kicked":
                status = "🚫 Bị Đá"
            else:
                status = "👤 Thành Viên"
        except ApiTelegramException as e:
            if "User not found" in str(e):
                status = "❓ Không Có Trong Nhóm"
            else:
                status = f"⚠️ Lỗi: {e}"
        except Exception as e:
            status = f"⚠️ Lỗi: {e}"
    user_info_text = (
        "🎫 **THẺ THÔNG HÀNH** 🎫\n"
        f"🔑 **Mã Định Danh:** `{user_id}`\n"
        f"📝 **Họ Tên:** {first_name}\n"
        f"🪪 **Bí Danh:** @{username}\n"
        f"📍 **Địa Chỉ:** [{first_name}]({user_link})\n"
        f"✨ **Trạng thái:** {status}\n"
    )
    return user_info_text

@bot.message_handler(commands=['thongtin'])
def user_info(message):
    chat_id = message.chat.id
    if message.reply_to_message:
        user = message.reply_to_message.from_user
        user_info_text = get_user_info_text(user, chat_id)
        bot.reply_to(message, user_info_text, parse_mode="Markdown", disable_web_page_preview=True)
    elif len(message.text.split()) > 1:
        arg = message.text.split()[1]
        try:
            user_id = int(arg)
            try:
                user = bot.get_chat_member(chat_id, user_id).user
                user_info_text = get_user_info_text(user, chat_id)
                bot.reply_to(message, user_info_text, parse_mode="Markdown", disable_web_page_preview=True)
            except ApiTelegramException as e:
                if "User not found" in str(e):
                    bot.reply_to(message, "Không tìm thấy người dùng với ID này.")
                else:
                    bot.reply_to(message, f"Lỗi: {e}")
        except ValueError:
            username = arg.replace("@", "")
            try:
                found = False
                for chat_member in bot.get_chat_administrators(chat_id):
                    if chat_member.user.username == username:
                        user = chat_member.user
                        user_info_text = get_user_info_text(user, chat_id)
                        bot.reply_to(message, user_info_text, parse_mode="Markdown", disable_web_page_preview=True)
                        found = True
                        break
                if not found:
                    bot.reply_to(message, "Không tìm thấy người dùng với username này trong nhóm.")
            except ApiTelegramException as e:
                bot.reply_to(message, f"Lỗi: {e}")
    else:
        bot.reply_to(message, "Sử dụng: /thongtin (reply tin nhắn) hoặc /thongtin <user_id> hoặc /thongtin <@username>")
bot.polling(none_stop=True)

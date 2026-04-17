from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def auth_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Connect Gmail + Google Calendar", callback_data="auth_google")],
        [InlineKeyboardButton("Connect Outlook + Teams Calendar", callback_data="auth_microsoft")],
    ])


def connected_accounts_keyboard(accounts: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = []
    for provider, email in accounts:
        label = f"{'Google' if provider == 'google' else 'Microsoft'}: {email}"
        rows.append([InlineKeyboardButton(f"❌ Remove {label}", callback_data=f"remove_{provider}_{email}")])
    rows.append([InlineKeyboardButton("➕ Add account", callback_data="add_account")])
    return InlineKeyboardMarkup(rows)

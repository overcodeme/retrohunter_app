import flet as ft
import json
import pyperclip
from typing import List, Dict, Any, Optional
from pathlib import Path

DATA_DIR = Path("data")
JSON_FILE = DATA_DIR / "accounts.json"

NETWORKS = [
    {"id": "evm", "label": "EVM", "field": "evm_private_key"},
    {"id": "sol", "label": "Solana", "field": "sol_private_key"},
    {"id": "sui", "label": "Sui", "field": "sui_private_key"},
    {"id": "aptos", "label": "Aptos", "field": "aptos_private_key"},
    {"id": "btc", "label": "Bitcoin", "field": "btc_private_key"},
]

def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)

def load_accounts() -> List[Dict[str, Any]]:
    ensure_data_dir()
    if not JSON_FILE.exists():
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for acc in data:
            for net in NETWORKS:
                field = net["field"]
                if field not in acc:
                    acc[field] = ""
        return data

def save_accounts(accounts: List[Dict[str, Any]]):
    ensure_data_dir()
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, indent=4, ensure_ascii=False)


class AccountsManager:
    def __init__(self, page: ft.Page, update_content_callback):
        self.page = page
        self.update_content = update_content_callback
        self.accounts = load_accounts()

        self.evm_field = None
        self.sol_field = None
        self.sui_field = None
        self.aptos_field = None
        self.btc_field = None
        self.email_field = None
        self.twitter_field = None
        self.discord_field = None
        self.dialog_modal = None
        self.editing_account_id = None

        self.import_dialog = None
        self.import_text_field = None

        self._cached_view = None
        self._revision = 0
        self._last_revision = -1

        self.selected_network = "evm"

    def _increment_revision(self):
        self._revision += 1

    def _copy_to_clipboard(self, e: ft.ControlEvent):
        text = e.control.data
        if text:
            try:
                pyperclip.copy(text)
            except Exception as ex:
                print(f"Copy failed: {ex}")

    @staticmethod
    def centered_header(text: str, width: int) -> ft.Container:
        return ft.Container(
            content=ft.Text(
                text,
                size=16,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            width=width,
            alignment=ft.Alignment.CENTER,
            padding=ft.padding.only(left=8, right=8, top=4, bottom=4),
        )

    @staticmethod
    def centered_cell(text: str, width: int, tooltip: str = "") -> ft.Container:
        return ft.Container(
            content=ft.Text(
                text,
                size=15,
                selectable=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                text_align=ft.TextAlign.CENTER,
            ),
            width=width,
            alignment=ft.Alignment.CENTER,
            padding=ft.padding.only(left=8, right=8, top=4, bottom=4),
            tooltip=tooltip,
        )

    def on_network_change(self, e):
        # В зависимости от версии Flet значение может быть в e.data или e.control.value
        self.selected_network = e.data if hasattr(e, 'data') else e.control.value
        self._increment_revision()
        self.update_content(self.get_view())

    def _build_view(self) -> ft.Container:
        header = ft.Row([
            ft.Text("Wallets list", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.ElevatedButton(
                "Import wallets",
                icon=ft.Icons.UPLOAD_FILE,
                on_click=self.open_import_dialog,
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.GREEN_600,
                ),
            ),
            ft.ElevatedButton(
                "Add wallet",
                icon=ft.Icons.ADD,
                on_click=self.open_add_account_dialog,
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.BLUE_600,
                ),
            ),
        ])

        stats_row = ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, size=20, color=ft.Colors.BLUE_400),
                    ft.Text(f"Total accounts: {len(self.accounts)}", size=16, weight=ft.FontWeight.W_500),
                ], spacing=10),
                padding=ft.padding.only(left=15, right=15, top=10, bottom=10),
                border_radius=20,
                bgcolor=ft.Colors.GREY_900,
            )
        ], alignment=ft.MainAxisAlignment.START)

        col_widths = {
            "id": 70,
            "key": 300,
            "email": 280,
            "twitter": 250,
            "discord": 250,
            "actions": 160,
        }
        key_text_width = 270

        # Dropdown с жирным шрифтом и центрированным текстом
        network_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(net["id"], net["label"]) for net in NETWORKS],
            value=self.selected_network,
            width=col_widths["key"] - 20,
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            text_align=ft.TextAlign.CENTER,
        )
        network_dropdown.on_select = self.on_network_change

        # Центрируем сам Dropdown внутри контейнера
        dropdown_container = ft.Container(
            content=network_dropdown,
            alignment=ft.Alignment.CENTER,
        )

        header_key_cell = ft.Container(
            content=dropdown_container,
            width=col_widths["key"],
            alignment=ft.Alignment.CENTER,
            padding=ft.padding.only(left=8, right=8, top=4, bottom=4),
        )

        header_row = ft.Container(
            content=ft.Row([
                self.centered_header("ID", col_widths["id"]),
                header_key_cell,
                self.centered_header("Email", col_widths["email"]),
                self.centered_header("Twitter", col_widths["twitter"]),
                self.centered_header("Discord", col_widths["discord"]),
                self.centered_header("Actions", col_widths["actions"]),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            border=ft.Border(
                top=ft.BorderSide(1, ft.Colors.GREY_800),
                left=ft.BorderSide(1, ft.Colors.GREY_800),
                right=ft.BorderSide(1, ft.Colors.GREY_800),
                bottom=ft.BorderSide(1, ft.Colors.GREY_800),
            ),
            bgcolor=ft.Colors.GREY_900,
        )

        if self.accounts:
            rows_content = []
            for acc in self.accounts:
                delete_btn = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=ft.Colors.RED_400,
                    tooltip="Delete an account",
                    data=acc.get("id"),
                    on_click=self.delete_account,
                    width=32,
                    height=32,
                    padding=0,
                    icon_size=20,
                )
                edit_btn = ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    icon_color=ft.Colors.BLUE_400,
                    tooltip="Edit an account",
                    data=acc.get("id"),
                    on_click=self.open_edit_account_dialog,
                    width=32,
                    height=32,
                    padding=0,
                    icon_size=20,
                )

                key_field = next((n["field"] for n in NETWORKS if n["id"] == self.selected_network), "evm_private_key")
                full_key = acc.get(key_field, "")
                display_key = full_key[:8] + "..." + full_key[-4:] if len(full_key) > 12 else full_key

                copy_btn = ft.IconButton(
                    icon=ft.Icons.CONTENT_COPY,
                    icon_size=16,
                    tooltip=f"Copy {self.selected_network.upper()} key",
                    data=full_key,
                    on_click=self._copy_to_clipboard,
                    width=24,
                    height=24,
                    padding=0,
                )
                key_cell_content = ft.Row([
                    self.centered_cell(display_key, key_text_width, tooltip=full_key),
                    copy_btn,
                ], spacing=0, alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                key_cell = ft.Container(
                    content=key_cell_content,
                    width=col_widths["key"],
                    alignment=ft.Alignment.CENTER,
                )

                row = ft.Container(
                    content=ft.Row([
                        self.centered_cell(str(acc.get("id", "")), col_widths["id"]),
                        key_cell,
                        self.centered_cell(acc.get("email", ""), col_widths["email"], tooltip=acc.get("email", "")),
                        self.centered_cell(acc.get("twitter_token", ""), col_widths["twitter"], tooltip=acc.get("twitter_token", "")),
                        self.centered_cell(acc.get("discord_token", ""), col_widths["discord"], tooltip=acc.get("discord_token", "")),
                        ft.Container(
                            content=ft.Row([edit_btn, delete_btn], spacing=2, alignment=ft.MainAxisAlignment.CENTER),
                            width=col_widths["actions"],
                            alignment=ft.Alignment.CENTER,
                        ),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    border=ft.Border(
                        left=ft.BorderSide(1, ft.Colors.GREY_800),
                        right=ft.BorderSide(1, ft.Colors.GREY_800),
                        bottom=ft.BorderSide(1, ft.Colors.GREY_800),
                    ),
                )
                rows_content.append(row)

            body = ft.Container(
                content=ft.Column(
                    rows_content,
                    scroll=ft.ScrollMode.ALWAYS,
                ),
                height=500,
                border=ft.Border(
                    left=ft.BorderSide(1, ft.Colors.GREY_800),
                    right=ft.BorderSide(1, ft.Colors.GREY_800),
                    bottom=ft.BorderSide(1, ft.Colors.GREY_800),
                ),
            )

            total_width = sum(col_widths.values()) + 8 * (len(col_widths) - 1)
            header_row.width = total_width
            body.width = total_width

            table_content = ft.Column([
                header_row,
                body,
            ])

            table_container = ft.Container(
                content=ft.Row(
                    [table_content],
                    scroll=ft.ScrollMode.ALWAYS,
                ),
                height=550,
                alignment=ft.Alignment.CENTER,
            )
        else:
            table_container = ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ACCOUNT_BALANCE_OUTLINED, size=64, color=ft.Colors.GREY_600),
                    ft.Text("No wallets yet", size=20, color=ft.Colors.GREY_400),
                    ft.Text("Click 'Add wallet' to add a wallet", color=ft.Colors.GREY_500),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=50,
                alignment=ft.Alignment.CENTER,
                height=400,
            )

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=20, color=ft.Colors.GREY_800),
                stats_row,
                ft.Container(height=20),
                table_container,
            ]),
            padding=20,
        )

    def get_view(self) -> ft.Container:
        if self._cached_view is None or self._revision != self._last_revision:
            self._cached_view = self._build_view()
            self._last_revision = self._revision
        return self._cached_view

    # ---------- ИМПОРТ ----------
    def open_import_dialog(self, e: ft.ControlEvent = None):
        self.import_text_field = ft.TextField(
            label="Paste accounts data (one per line)",
            multiline=True,
            min_lines=10,
            max_lines=20,
            hint_text="Format: evm_key|sol_key|sui_key|aptos_key|btc_key|email|twitter_token|discord_token\n(backward compatible: evm_key|sol_key|email|twitter_token|discord_token)",
        )

        self.import_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Import wallets from text"),
            content=ft.Container(
                content=ft.Column([
                    self.import_text_field,
                    ft.Text("Each line should contain fields separated by '|'", size=12, color=ft.Colors.GREY_400),
                ], scroll=ft.ScrollMode.AUTO),
                width=600,
                padding=10,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_import_dialog),
                ft.ElevatedButton("Import", on_click=self.import_from_text),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(self.import_dialog)
        self.page.update()

    def close_import_dialog(self, e: ft.ControlEvent = None):
        if self.import_dialog:
            self.import_dialog.open = False
            self.page.update()

    def import_from_text(self, e: ft.ControlEvent = None):
        text = self.import_text_field.value
        if not text:
            return
        lines = text.strip().split('\n')
        new_accounts = []
        max_id = max([acc["id"] for acc in self.accounts], default=0)
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [part.strip() for part in line.split('|')]
            if len(parts) == 5:
                evm = parts[0]
                sol = parts[1]
                email = parts[2]
                twitter = parts[3]
                discord = parts[4]
                sui = aptos = btc = ""
            elif len(parts) >= 8:
                evm = parts[0]
                sol = parts[1]
                sui = parts[2]
                aptos = parts[3]
                btc = parts[4]
                email = parts[5]
                twitter = parts[6]
                discord = parts[7]
            else:
                print(f"Line {line_num}: недостаточно полей ({len(parts)}), ожидается 5 или 8, разделённых '|'.")
                continue

            max_id += 1
            new_acc = {
                "id": max_id,
                "evm_private_key": evm,
                "sol_private_key": sol,
                "sui_private_key": sui,
                "aptos_private_key": aptos,
                "btc_private_key": btc,
                "email": email,
                "twitter_token": twitter,
                "discord_token": discord,
            }
            new_accounts.append(new_acc)
        if new_accounts:
            self.accounts.extend(new_accounts)
            save_accounts(self.accounts)
            self._increment_revision()
            self.close_import_dialog()
            self.update_content(self.get_view())
        else:
            print("Нет корректных аккаунтов для импорта.")

    # ---------- ДИАЛОГ ДОБАВЛЕНИЯ/РЕДАКТИРОВАНИЯ ----------
    def open_add_account_dialog(self, e: ft.ControlEvent = None):
        self.editing_account_id = None
        self._show_account_dialog()

    def open_edit_account_dialog(self, e: ft.ControlEvent):
        account_id = e.control.data
        self.editing_account_id = account_id
        account = next((acc for acc in self.accounts if acc["id"] == account_id), None)
        if account:
            self._show_account_dialog(account)

    def _show_account_dialog(self, account: Optional[Dict] = None):
        self.evm_field = ft.TextField(
            label="EVM Private Key",
            value=account.get("evm_private_key") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3,
        )
        self.sol_field = ft.TextField(
            label="Solana Private Key",
            value=account.get("sol_private_key") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3,
        )
        self.sui_field = ft.TextField(
            label="Sui Private Key",
            value=account.get("sui_private_key") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3,
        )
        self.aptos_field = ft.TextField(
            label="Aptos Private Key",
            value=account.get("aptos_private_key") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3,
        )
        self.btc_field = ft.TextField(
            label="Bitcoin Private Key (WIF)",
            value=account.get("btc_private_key") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3,
        )
        self.email_field = ft.TextField(
            label="Email (log:pass)",
            value=account.get("email") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3,
        )
        self.twitter_field = ft.TextField(
            label="Twitter token",
            value=account.get("twitter_token") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3,
        )
        self.discord_field = ft.TextField(
            label="Discord token",
            value=account.get("discord_token") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3,
        )

        self.dialog_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit account" if account else "Add new account"),
            content=ft.Container(
                content=ft.Column([
                    self.evm_field,
                    self.sol_field,
                    self.sui_field,
                    self.aptos_field,
                    self.btc_field,
                    self.email_field,
                    self.twitter_field,
                    self.discord_field,
                ], scroll=ft.ScrollMode.AUTO, height=500),
                width=550,
            ),
            actions=[
                ft.TextButton("Save", on_click=self.save_account),
                ft.TextButton("Cancel", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(self.dialog_modal)
        self.page.update()

    def save_account(self, e: ft.ControlEvent = None):
        if self.editing_account_id is None:
            new_id = max([acc["id"] for acc in self.accounts], default=0) + 1
            new_account = {
                "id": new_id,
                "evm_private_key": self.evm_field.value or "",
                "sol_private_key": self.sol_field.value or "",
                "sui_private_key": self.sui_field.value or "",
                "aptos_private_key": self.aptos_field.value or "",
                "btc_private_key": self.btc_field.value or "",
                "email": self.email_field.value or "",
                "twitter_token": self.twitter_field.value or "",
                "discord_token": self.discord_field.value or "",
            }
            self.accounts.append(new_account)
        else:
            for acc in self.accounts:
                if acc["id"] == self.editing_account_id:
                    acc.update({
                        "evm_private_key": self.evm_field.value or "",
                        "sol_private_key": self.sol_field.value or "",
                        "sui_private_key": self.sui_field.value or "",
                        "aptos_private_key": self.aptos_field.value or "",
                        "btc_private_key": self.btc_field.value or "",
                        "email": self.email_field.value or "",
                        "twitter_token": self.twitter_field.value or "",
                        "discord_token": self.discord_field.value or "",
                    })
                    break
        save_accounts(self.accounts)
        self._increment_revision()
        self.close_dialog()
        self.update_content(self.get_view())

    def close_dialog(self, e: ft.ControlEvent = None):
        if self.dialog_modal:
            self.dialog_modal.open = False
            self.page.update()

    def _confirm_delete(self, account_id):
        def close_dialog(e):
            dlg.open = False
            self.page.update()
        def confirm(e):
            self._delete_account(account_id)
            close_dialog(e)
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirm deletion"),
            content=ft.Text("Are you sure you want to delete this account?"),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.ElevatedButton("Delete", on_click=confirm, color=ft.Colors.RED_400),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def _delete_account(self, account_id):
        self.accounts = [acc for acc in self.accounts if acc.get("id") != account_id]
        save_accounts(self.accounts)
        self._increment_revision()
        self.update_content(self.get_view())

    def delete_account(self, e: ft.ControlEvent):
        account_id = e.control.data
        self._confirm_delete(account_id)
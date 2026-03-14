import flet as ft
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from web3 import Web3
from solders.keypair import Keypair
import base58

DATA_DIR = Path("data")
JSON_FILE = DATA_DIR / "accounts.json"

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
            if "evm_address" not in acc and acc.get("evm_private_key"):
                addr = derive_evm_address(acc["evm_private_key"])
                if addr:
                    acc["evm_address"] = addr
            if "solana_address" not in acc and acc.get("sol_private_key"):
                addr = derive_solana_address(acc["sol_private_key"])
                if addr:
                    acc["solana_address"] = addr
        return data

def save_accounts(accounts: List[Dict[str, Any]]):
    ensure_data_dir()
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, indent=4, ensure_ascii=False)

def derive_evm_address(private_key: str) -> Optional[str]:
    """Получает адрес EVM из приватного ключа (с префиксом 0x или без)"""
    try:
        if private_key.startswith('0x'):
            private_key = private_key[2:]
        account = Web3().eth.account.from_key(private_key)
        return account.address
    except Exception:
        return None

def derive_solana_address(private_key: str) -> Optional[str]:
    """Получает адрес Solana из приватного ключа (base58 или байты)"""
    try:
        # Пытаемся интерпретировать как base58 строку (стандартный формат)
        keypair = Keypair.from_base58_string(private_key)
        return str(keypair.pubkey())
    except:
        try:
            # Альтернативно, возможно это байты в base58
            decoded = base58.b58decode(private_key)
            if len(decoded) == 64:
                keypair = Keypair.from_bytes(decoded)
                return str(keypair.pubkey())
        except:
            pass
    return None


class AccountsManager:
    def __init__(self, page: ft.Page, update_content_callback):
        self.page = page
        self.update_content = update_content_callback
        self.accounts = load_accounts()

        # Поля для диалога
        self.evm_field = None
        self.sol_field = None
        self.email_field = None
        self.twitter_field = None
        self.discord_field = None
        self.dialog_modal = None
        self.editing_account_id = None

        # Диалог для импорта
        self.import_dialog = None
        self.import_text_field = None

        # Кэширование представления
        self._cached_view = None
        self._revision = 0
        self._last_revision = -1

    def _increment_revision(self):
        self._revision += 1

    @staticmethod
    def centered_header(text: str, width: int) -> ft.Container:
        """Ячейка заголовка с центрированием"""
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
            padding=5,
        )

    @staticmethod
    def cell(text: str, width: int, tooltip: str = "") -> ft.Container:
        """Ячейка данных с выравниванием по левому краю (по умолчанию)"""
        return ft.Container(
            content=ft.Text(
                text,
                size=15,
                selectable=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                text_align=ft.TextAlign.LEFT,
            ),
            width=width,
            alignment=ft.Alignment.CENTER_LEFT,
            padding=ft.padding.only(left=8, right=8, top=4, bottom=4),
            tooltip=tooltip,
        )

    @staticmethod
    def centered_cell(text: str, width: int, tooltip: str = "") -> ft.Container:
        """Ячейка данных с центрированием"""
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

    def _get_account_display(self, acc: Dict, network: str) -> str:
        """Возвращает строку для отображения аккаунта (адрес или ключ)"""
        if network == "evm":
            address = acc.get("evm_address")
            if address:
                return address[:4] + "..." + address[-4:]
            key = acc.get("evm_private_key", "")
            if key:
                return key[:4] + "..." + key[-4:]
            return "No EVM"
        else:  # solana
            address = acc.get("solana_address")
            if address:
                return address[:4] + "..." + address[-4:]
            key = acc.get("sol_private_key", "")
            if key:
                return key[:4] + "..." + key[-4:]
            return "No Solana"

    def _build_view(self) -> ft.Container:
        """Строит представление раздела аккаунтов"""
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
            "id": 50,
            "evm": 220,
            "sol": 220,
            "email": 250,
            "twitter": 220,
            "discord": 220,
            "actions": 120,
        }

        header_row = ft.Container(
            content=ft.Row([
                self.centered_header("ID", col_widths["id"]),
                self.centered_header("EVM Address", col_widths["evm"]),
                self.centered_header("Solana Address", col_widths["sol"]),
                self.centered_header("Email", col_widths["email"]),
                self.centered_header("Twitter", col_widths["twitter"]),
                self.centered_header("Discord", col_widths["discord"]),
                self.centered_header("Actions", col_widths["actions"]),
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            border=ft.Border(
                top=ft.BorderSide(1, ft.Colors.GREY_800),
                left=ft.BorderSide(1, ft.Colors.GREY_800),
                right=ft.BorderSide(1, ft.Colors.GREY_800),
                bottom=ft.BorderSide(1, ft.Colors.GREY_800),
            ),
            bgcolor=ft.Colors.GREY_900,
            padding=5,
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

                evm_display = self._get_account_display(acc, "evm")
                sol_display = self._get_account_display(acc, "solana")

                row = ft.Container(
                    content=ft.Row([
                        self.centered_cell(str(acc.get("id", "")), col_widths["id"]),
                        self.cell(evm_display, col_widths["evm"], tooltip=acc.get("evm_private_key", "")),
                        self.cell(sol_display, col_widths["sol"], tooltip=acc.get("sol_private_key", "")),
                        self.cell(acc.get("email", ""), col_widths["email"], tooltip=acc.get("email", "")),
                        self.cell(acc.get("twitter_token", ""), col_widths["twitter"], tooltip=acc.get("twitter_token", "")),
                        self.cell(acc.get("discord_token", ""), col_widths["discord"], tooltip=acc.get("discord_token", "")),
                        ft.Container(
                            content=ft.Row([edit_btn, delete_btn], spacing=2, alignment=ft.MainAxisAlignment.CENTER),
                            width=col_widths["actions"],
                            alignment=ft.Alignment.CENTER,
                        ),
                    ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    border=ft.Border(
                        left=ft.BorderSide(1, ft.Colors.GREY_800),
                        right=ft.BorderSide(1, ft.Colors.GREY_800),
                        bottom=ft.BorderSide(1, ft.Colors.GREY_800),
                    ),
                    padding=5,
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
        """Возвращает представление раздела аккаунтов с кэшированием"""
        if self._cached_view is None or self._revision != self._last_revision:
            self._cached_view = self._build_view()
            self._last_revision = self._revision
        return self._cached_view

    def _create_table_rows(self) -> List[ft.DataRow]:
        # Не используется
        return []

    # ---------- ИМПОРТ ЧЕРЕЗ ТЕКСТОВОЕ ПОЛЕ ----------
    def open_import_dialog(self, e: ft.ControlEvent = None):
        self.import_text_field = ft.TextField(
            label="Paste accounts data (one per line)",
            multiline=True,
            min_lines=10,
            max_lines=20,
            hint_text="Format: evm_key|sol_key|email|twitter_token|discord_token",
        )

        self.import_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Import wallets from text"),
            content=ft.Container(
                content=ft.Column([
                    self.import_text_field,
                    ft.Text("Each line should contain 5 fields separated by '|'", size=12, color=ft.Colors.GREY_400),
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

    def _derive_addresses(self, account: Dict):
        """Вычисляет адреса из приватных ключей и добавляет их в словарь"""
        evm_key = account.get("evm_private_key")
        sol_key = account.get("sol_private_key")
        if evm_key:
            addr = derive_evm_address(evm_key)
            if addr:
                account["evm_address"] = addr
        if sol_key:
            addr = derive_solana_address(sol_key)
            if addr:
                account["solana_address"] = addr

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
            if len(parts) < 5:
                print(f"Line {line_num}: недостаточно полей ({len(parts)}), ожидается 5, разделённых '|'.")
                continue

            evm = parts[0]
            sol = parts[1]
            email = parts[2]
            twitter = parts[3]
            discord = parts[4]

            max_id += 1
            new_acc = {
                "id": max_id,
                "evm_private_key": evm,
                "sol_private_key": sol,
                "email": email,
                "twitter_token": twitter,
                "discord_token": discord,
            }
            self._derive_addresses(new_acc)
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
                    self.email_field,
                    self.twitter_field,
                    self.discord_field,
                ], scroll=ft.ScrollMode.AUTO, height=400),
                width=500,
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
                "email": self.email_field.value or "",
                "twitter_token": self.twitter_field.value or "",
                "discord_token": self.discord_field.value or "",
            }
            self._derive_addresses(new_account)
            self.accounts.append(new_account)
        else:
            for acc in self.accounts:
                if acc["id"] == self.editing_account_id:
                    acc.update({
                        "evm_private_key": self.evm_field.value or "",
                        "sol_private_key": self.sol_field.value or "",
                        "email": self.email_field.value or "",
                        "twitter_token": self.twitter_field.value or "",
                        "discord_token": self.discord_field.value or "",
                    })
                    self._derive_addresses(acc)
                    break
        save_accounts(self.accounts)
        self._increment_revision()
        self.close_dialog()
        self.update_content(self.get_view())

    def close_dialog(self, e: ft.ControlEvent = None):
        if self.dialog_modal:
            self.dialog_modal.open = False
            self.page.update()

    # ---------- ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ ----------
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
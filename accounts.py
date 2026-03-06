import flet as ft
import json
from typing import List, Dict, Any, Optional
from pathlib import Path


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
        return json.load(f)
    
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
        self.email_field = None
        self.twitter_field = None
        self.discord_field = None
        self.dialog_modal = None
        self.editing_account_id = None

    @staticmethod
    def centered_header(text: str, width: int = 100) -> ft.DataColumn:
        """Создает центрированный заголовок с фиксированной шириной"""
        return ft.DataColumn(
            ft.Container(
                content=ft.Text(
                    text, 
                    size=12, 
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                ),
                width=width, 
                alignment=ft.Alignment.CENTER,
            )
        )


    def get_view(self) -> ft.Container:
        """Возвращает представление для раздела аккаунтов"""
        table_rows = self._create_table_rows()

        header = ft.Row([
            ft.Text("Wallets list", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.ElevatedButton(
                "Add wallet",
                icon=ft.Icons.ADD,
                on_click=self.open_add_account_dialog,
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.BLUE_600
                )
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
                bgcolor=ft.Colors.GREY_900
            )
        ], alignment=ft.MainAxisAlignment.END)

        if self.accounts:
            table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("№", size=12)),
                    self.centered_header("EVM Key", 120),
                    self.centered_header("Solana Key", 120),
                    self.centered_header("Email", 150),
                    self.centered_header("Twitter", 120),
                    self.centered_header("Discord", 120),
                    self.centered_header("Actions", 80),
                ],
                rows=table_rows,
                border=ft.Border.all(1, ft.Colors.GREY_800),
                vertical_lines=ft.BorderSide(1, ft.Colors.GREY_800),
                horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_800),
                column_spacing=15,
            )

            table_container = ft.Container(
                content=ft.Row([
                    table
                ], scroll=ft.ScrollMode.ALWAYS)
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
                table_container
            ]),
            padding=20
        )

        
    def _create_table_rows(self) -> List[ft.DataRow]:
        rows = []

        for acc in self.accounts:
            delete_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                tooltip="Delete an account",
                data=acc.get("id"),
                on_click=self.delete_account,
                width=32,
                padding=0,
                height=32
            )

            edit_btn = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.BLUE_400,
                tooltip="Edit an account",
                data=acc.get("id"),
                on_click=self.open_edit_account_dialog,
                width=32,
                padding=0,
                height=32
            )

            id_text = ft.Text(
                str(acc.get("id", "")),
                size=12,
                width=40
            )

            evm_text = ft.Text(
                acc.get("evm_private_key", ""),
                size=12,
                selectable=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                width=120,
                tooltip=acc.get("evm_private_key", "")
            )

            sol_text = ft.Text(
                acc.get("sol_private_key", ""),
                size=12,
                selectable=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                width=120,
                tooltip=acc.get("sol_private_key", ""),  
            )

            email_text = ft.Text(
                acc.get("email", ""),
                size=12,
                selectable=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                width=150,
                tooltip=acc.get("email", ""), 
            )

            twitter_text = ft.Text(
                acc.get("twitter_token", ""),
                size=12,
                selectable=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                width=120,
                tooltip=acc.get("twitter_token", ""),
            )

            discord_text = ft.Text(
                acc.get("discord_token", ""),
                size=12,
                selectable=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                width=120,
                tooltip=acc.get("discord_token", ""),
            )

            row = ft.DataRow(
                cells=[
                    ft.DataCell(id_text),
                    ft.DataCell(evm_text),
                    ft.DataCell(sol_text),
                    ft.DataCell(email_text),
                    ft.DataCell(twitter_text),
                    ft.DataCell(discord_text),
                    ft.DataCell(ft.Row([edit_btn, delete_btn], spacing=2)),
                ]
            )
            rows.append(row)
        
        return rows


    def open_add_account_dialog(self, e: ft.ControlEvent = None):
        self.editing_account_id = None
        self._show_account_dialog()


    def open_edit_account_dialog(self, e: ft.ControlEvent = None):
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
            max_lines=3
        )
        self.sol_field = ft.TextField(
            label="Solana Private Key",
            value=account.get("sol_private_key") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3
        )
        self.email_field = ft.TextField(
            label="Email (log:pass)",
            value=account.get("email") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3
        )
        self.twitter_field = ft.TextField(
            label="Twitter token",
            value=account.get("twitter_token") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3
        )
        self.discord_field = ft.TextField(
            label="Discord token",
            value=account.get("discord_token") if account else "",
            multiline=True,
            min_lines=1,
            max_lines=3
        )

        self.dialog_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit an account" if account else "Add new account"),
            content=ft.Container(
                content=ft.Column([
                    self.evm_field,
                    self.sol_field,
                    self.email_field,
                    self.twitter_field,
                    self.discord_field
                ], scroll=ft.ScrollMode.AUTO, height=400),
                width=500
            ),
            actions=[
                ft.TextButton("Add", on_click=self.save_account),
                ft.TextButton("Cancel", on_click=self.close_dialog)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        self.page.show_dialog(self.dialog_modal)
        self.page.update()


    def save_account(self, e: ft.ControlEvent = None):
        if self.editing_account_id is None:
            new_id = max([acc["id"] for acc in self.accounts], default=0) + 1
            new_account = {
                "id": new_id,
                "evm_private_key": self.evm_field.value,
                "sol_private_key": self.sol_field.value,
                "email": self.email_field.value,
                "twitter_token": self.twitter_field.value,
                "discord_token": self.discord_field.value
            }
            self.accounts.append(new_account)
        else:
            for acc in self.accounts:
                if acc["id"] == self.editing_account_id:
                    acc.update({
                        "evm_private_key": self.evm_field.value,
                        "sol_private_key": self.sol_field.value,
                        "email": self.email_field.value,
                        "twitter_token": self.twitter_field.value,
                        "discord_token": self.discord_field.value 
                    })
                    break
        save_accounts(self.accounts)
        self.close_dialog()
        self.update_content(self.get_view())


    def close_dialog(self, e: ft.ControlEvent = None):
        self.dialog_modal.open = False
        self.page.update()

    
    def delete_account(self, e: ft.ControlEvent):
        account_id = e.control.data
        self.accounts = [acc for acc in self.accounts if acc.get("id") != account_id]
        save_accounts(self.accounts)
        self.update_content(self.get_view())
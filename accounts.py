import flet as ft
import json
import os
from typing import List, Dict, Any
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

        # Поля для диалога добавления
        self.evm_field = None
        self.sol_field = None
        self.email_field = None
        self.twitter_field = None
        self.discord_field = None
        self.dlg_modal = None

    def get_view(self) -> ft.Container:
        """Возвращает представление для раздела аккаунтов"""

        table_rows = self._create_table_rows()

        header = ft.Row([
            ft.Text("Wallets management", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.ElevatedButton(
                "Add account",
                icon=ft.Icons.ADD,
                on_click=self.open_add_account_dialog,
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.BLUE_600
                )
            ),
        ])

        stats_row = self._create_stats_row()

        if self.accounts:
            table = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("ID")),
                    ft.DataColumn(ft.Text("EVM Key")),
                    ft.DataColumn(ft.Text("Solana Key")),
                    ft.DataColumn(ft.Text("Email")),
                    ft.DataColumn(ft.Text("Twitter")),
                    ft.DataColumn(ft.Text("Discord")),
                    ft.DataColumn(ft.Text("Actions"))
                ],
                rows=table_rows,
                border=ft.Border.all(1, ft.Colors.GREY_800),
                vertical_lines=ft.BorderSide(1, ft.Colors.GREY_800),
                horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_800)
            )
        else:
            table = ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ACCOUNT_BALANCE_OUTLINED, size=64, color=ft.Colors.GREY_600),
                    ft.Text("No accounts yet", size=20, color=ft.Colors.GREY_400),
                    ft.Text("Click 'Add account' to add an account", color=ft.Colors.GREY_500),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=50,
                alignment=ft.Alignment.CENTER
            )

        return ft.Container(
            content=ft.Column([
                header, 
                ft.Divider(height=20, color=ft.Colors.GREY_800),
                ft.Container(height=20),
                ft.Text("Accounts list", size=18, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=ft.Column([
                        table
                    ], scroll=ft.ScrollMode.AUTO),
                    height=400,
                    border=ft.Border.all(1, ft.Colors.GREY_800),
                    border_radius=10,
                    padding=10
                )
            ]),
            padding=20
        )

        
    def _create_table_rows(self) -> List[ft.Container]:
        """Создает строки таблицы с аккаунтами"""

    
    def _create_stats_row(self) -> ft.Row:
        """Создает строку со статистикой"""

    def add_account(self, e):
        """Добавление нового аккаунта"""
        max_id = max([acc.get("id", 0) for acc in self.accounts]) if self.accounts else 0

        new_account = {
            "id": max_id + 1,
            "evm_private_key": self.evm_field.value or "",
            "sol_private_key": self.sol_field.value or "",
            "email": self.email_field.value or "",
            "twitter_token": self.twitter_field.value or "",
            "discord_token": self.discord_field.value or ""
        }

        self.accounts.append(new_account)
        save_accounts(self.accounts)

        self.evm_field.value = ""
        self.sol_field.value = ""
        self.email_field.value = ""
        self.twitter_field.value = ""
        self.discord_field.value = ""

        self.dlg_modal.open = False


    def delete_account(self, e: ft.ControlEvent):
        """Удаление аккаунта по ID"""


    def open_add_account_dialog(self, e):
        """Открытие диалога для добавления нового аккаунта"""

    
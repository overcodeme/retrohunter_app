import flet as ft
import json
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
        self.dialog_modal = None


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

        # Вывод статистики (общее кол-во аккаунтов)
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

        # Вывод аккаунтов
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
                stats_row,
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

        
    def _create_table_rows(self) -> List[ft.DataRow]:
        """Создает строки таблицы с аккаунтами"""
        rows = []

        for acc in self.accounts:
            delete_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                tooltip="Delete account",
                data=acc.get("id"),
                on_click=self.delete_account
            )

            edit_btn = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.BLUE_400,
                tooltip="Edit account (coming soon)",
                disabled=True
            )

            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(acc.get("id", "")))),
                    ft.DataCell(ft.Text(acc.get("evm_private_key", ""), selectable=True)),
                    ft.DataCell(ft.Text(acc.get("sol_private_key", ""), selectable=True)),  # Исправлено
                    ft.DataCell(ft.Text(acc.get("email", ""), selectable=True)),
                    ft.DataCell(ft.Text(acc.get("twitter_token", ""), selectable=True)),
                    ft.DataCell(ft.Text(acc.get("discord_token", ""), selectable=True)),
                    ft.DataCell(ft.Row([edit_btn, delete_btn], spacing=5))
                ]
            )
            rows.append(row)
        
        return rows


    def add_account(self, e: ft.ControlEvent = None):  # Добавлен параметр
        """Добавление нового аккаунта"""
        max_id = max([acc.get("id", 0) for acc in self.accounts]) if self.accounts else 0

        new_account = {
            "id": max_id + 1,
            "evm_private_key": self.evm_field.value or "",
            "sol_private_key": self.sol_field.value or "",  # Унифицировано
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

        self.dialog_modal.open = False
        self.page.update()

        self.update_content(self.get_view())


    def delete_account(self, e: ft.ControlEvent):
        """Удаление аккаунта по ID"""
        account_id = e.control.data
        self.accounts = [acc for acc in self.accounts if acc.get("id") != account_id]
        save_accounts(self.accounts)
        self.update_content(self.get_view())


    def open_add_account_dialog(self, e: ft.ControlEvent = None):  # Добавлен параметр
        """Открытие диалога для добавления нового аккаунта"""
        self.evm_field = ft.TextField(label="EVM Private Key", multiline=True, min_lines=1, max_lines=3)
        self.sol_field = ft.TextField(label="Solana Private Key", multiline=True, min_lines=1, max_lines=3)  # Исправлено
        self.email_field = ft.TextField(label="Email (log:pass)", multiline=True, min_lines=1, max_lines=3)
        self.twitter_field = ft.TextField(label="Twitter token", multiline=True, min_lines=1, max_lines=3)
        self.discord_field = ft.TextField(label="Discord token", multiline=True, min_lines=1, max_lines=3)

        self.dialog_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add new account"),
            content=ft.Container(
                content=ft.Column([
                    self.evm_field,
                    self.sol_field,
                    self.email_field,
                    self.twitter_field,
                    self.discord_field
                ], scroll=ft.ScrollMode.AUTO, height=400),
                width=500,
            ),
            actions=[
                ft.TextButton("Add", on_click=self.add_account),
                ft.TextButton("Cancel", on_click=self.close_add_account_dialog)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(self.dialog_modal)
        self.page.update()

    
    def close_add_account_dialog(self, e: ft.ControlEvent = None):  # Добавлен параметр
        self.dialog_modal.open = False
        self.page.update()
import flet as ft
import json
import csv
import pyperclip
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from eth_account import Account as EthAccount
from solders.keypair import Keypair as SolKeypair
from aptos_sdk.account import Account as AptosAccount
from bitcoinlib.keys import HDKey

DATA_DIR = Path("data")
JSON_FILE = DATA_DIR / "accounts.json"

NETWORKS = [
    {"id": "evm", "label": "EVM", "field": "evm_private_key", "address_field": "evm_address"},
    {"id": "sol", "label": "Solana", "field": "sol_private_key", "address_field": "solana_address"},
    {"id": "sui", "label": "Sui", "field": "sui_private_key", "address_field": "sui_address"},
    {"id": "aptos", "label": "Aptos", "field": "aptos_private_key", "address_field": "aptos_address"},
    {"id": "btc", "label": "Bitcoin", "field": "btc_private_key", "address_field": "btc_address"},
]

def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)

def load_accounts() -> List[Dict[str, Any]]:
    ensure_data_dir()
    if not JSON_FILE.exists():
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        for acc in data:
            for net in NETWORKS:
                field = net["field"]
                if field not in acc:
                    acc[field] = ""
                address_field = net["address_field"]
                if address_field not in acc or not acc.get(address_field):
                    priv = acc.get(field, "")
                    if priv:
                        try:
                            acc[address_field] = derive_address(net["id"], priv)
                        except Exception:
                            acc[address_field] = ""
                    else:
                        acc[address_field] = ""
        return data

def save_accounts(accounts: List[Dict[str, Any]]):
    ensure_data_dir()
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=4, ensure_ascii=False)


def derive_address(network: str, priv_key: str) -> str:
    if not priv_key:
        return ""

    try:
        if network == "evm":
            acct = EthAccount.from_key(priv_key)
            return acct.address

        if network == "sol":
            try:
                kp = SolKeypair.from_base58_string(priv_key)
                return str(kp.pubkey())
            except:
                secret = bytes.fromhex(priv_key)
                kp = SolKeypair.from_bytes(secret)
                return str(kp.pubkey())

        if network == "sui":
            import hashlib, binascii
            priv_bytes = bytes.fromhex(priv_key)
            pub_bytes = EthAccount.from_key(priv_bytes).public_key
            addr = hashlib.sha256(pub_bytes).digest()[:20]
            return "0x" + binascii.hexlify(addr).decode()

        if network == "aptos":
            acct = AptosAccount(priv_key)
            return acct.address().hex()

        if network == "btc":
            hd = HDKey(import_key=priv_key)
            return hd.address()
    except Exception as exc:
        print(f"[derive_address] {network} error: {exc}")
        return ""
    return ""


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
        self.file_picker = None

        self._cached_view = None
        self._revision = 0
        self._last_revision = -1

        self.selected_network = "evm"
        self.display_mode = "key"   # "key" или "address"
        self.show_only_with_key = False
        self.selected_account_ids = set()

    def _increment_revision(self):
        self._revision += 1

    def _close_dialog(self, dlg: ft.AlertDialog):
        dlg.open = False
        self.page.update()

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
        self.selected_network = e.data if hasattr(e, "data") else e.control.value
        self.selected_account_ids.clear()
        self._increment_revision()
        self.update_content(self.get_view())

    def on_display_mode_change(self, e):
        self.display_mode = e.data if hasattr(e, "data") else e.control.value
        self._increment_revision()
        self.update_content(self.get_view())

    def on_filter_key_change(self, e):
        self.show_only_with_key = e.control.value
        self.selected_account_ids.clear()
        self._increment_revision()
        self.update_content(self.get_view())

    def _get_account_display(self, acc: Dict, network: str) -> str:
        if self.display_mode == "key":
            for net in NETWORKS:
                if net["id"] == network:
                    return acc.get(net["field"], "")
        else:
            for net in NETWORKS:
                if net["id"] == network:
                    return acc.get(net["address_field"], "")
        return ""

    def _get_account_key(self, acc: Dict, network: str) -> str:
        for net in NETWORKS:
            if net["id"] == network:
                return acc.get(net["field"], "")
        return ""

    def _filter_accounts(self) -> List[Dict]:
        if not self.show_only_with_key:
            return self.accounts
        return [acc for acc in self.accounts if self._get_account_key(acc, self.selected_network)]

    def _export_to_csv(self, path: Path):
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            headers = [
                "id",
                "evm_private_key",
                "sol_private_key",
                "sui_private_key",
                "aptos_private_key",
                "btc_private_key",
                "email",
                "twitter_token",
                "discord_token",
            ]
            writer.writerow(headers)
            for acc in self.accounts:
                writer.writerow([acc.get(h, "") for h in headers])

    def _export_to_json(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.accounts, f, indent=4, ensure_ascii=False)

    def _export_dialog(self):
        def on_export_format(e):
            fmt = e.control.data
            self._show_export_file_dialog(fmt)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Export wallets"),
            content=ft.Column(
                [
                    ft.ElevatedButton("CSV", data="csv", on_click=on_export_format),
                    ft.ElevatedButton("JSON", data="json", on_click=on_export_format),
                ],
                spacing=10,
            ),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg))],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def _show_export_file_dialog(self, fmt: str):
        if not self.file_picker:
            self.file_picker = ft.FilePicker()
            self.page.overlay.append(self.file_picker)

        if hasattr(self.file_picker, "save_file"):
            self.file_picker.save_file(
                dialog_title="Save as",
                allowed_extensions=[fmt],
                on_result=lambda e: self._on_export_file_selected(e, fmt),
            )
        else:
            def on_confirm(e):
                p = Path(path_field.value)
                if p.parent.exists():
                    self._do_export(p, fmt)
                    self._close_dialog(dlg)
                else:
                    path_field.error_text = "Invalid path"
                    self.page.update()

            path_field = ft.TextField(label="File path", hint_text=f"path/to/export.{fmt}")
            dlg = ft.AlertDialog(
                title=ft.Text(f"Save as .{fmt}"),
                content=path_field,
                actions=[
                    ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
                    ft.ElevatedButton("Save", on_click=on_confirm),
                ],
            )
            self.page.show_dialog(dlg)

    def _on_export_file_selected(self, e, fmt: str):
        if e.path:
            self._do_export(Path(e.path), fmt)

    def _do_export(self, path: Path, fmt: str):
        try:
            if fmt == "csv":
                self._export_to_csv(path)
            else:
                self._export_to_json(path)
            self.page.snack_bar = ft.SnackBar(content=ft.Text(f"Exported to {path}"), open=True)
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(f"Export failed: {ex}"), open=True)
        self.page.update()

    def _bulk_edit_dialog(self):
        def on_save(e):
            field = field_dropdown.value
            value = value_field.value
            if not field or not value:
                return
            for acc in self.accounts:
                if acc["id"] in self.selected_account_ids:
                    acc[field] = value
            save_accounts(self.accounts)
            self._increment_revision()
            self.update_content(self.get_view())
            self._close_dialog(dlg)

        field_dropdown = ft.Dropdown(
            label="Field",
            options=[
                ft.dropdown.Option("email", "Email"),
                ft.dropdown.Option("twitter_token", "Twitter Token"),
                ft.dropdown.Option("discord_token", "Discord Token"),
            ],
            value="email",
        )
        value_field = ft.TextField(label="New value", multiline=True)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Bulk edit"),
            content=ft.Column([field_dropdown, value_field], spacing=10),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dlg)),
                ft.ElevatedButton("Apply", on_click=on_save),
            ],
        )
        self.page.show_dialog(dlg)

    def _build_view(self) -> ft.Container:
        header = ft.Row(
            [
                ft.Text("Wallets list", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.ElevatedButton(
                    "Export",
                    icon=ft.Icons.DOWNLOAD,
                    on_click=lambda _: self._export_dialog(),
                    style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.GREY_700),
                ),
                ft.ElevatedButton(
                    "Import wallets",
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=self.open_import_dialog,
                    style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.GREEN_600),
                ),
                ft.ElevatedButton(
                    "Add wallet",
                    icon=ft.Icons.ADD,
                    on_click=self.open_add_account_dialog,
                    style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE_600),
                ),
            ]
        )

        # Выбор сети (отдельный дропдаун слева)
        network_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(net["id"], net["label"]) for net in NETWORKS],
            value=self.selected_network,
            width=150,
        )
        network_dropdown.on_select = self.on_network_change

        select_all_btn = ft.TextButton("Select All", on_click=self._select_all)
        clear_all_btn = ft.TextButton("Clear All", on_click=self._clear_all)
        bulk_edit_btn = ft.ElevatedButton(
            "Bulk edit", icon=ft.Icons.EDIT, on_click=lambda _: self._bulk_edit_dialog()
        )

        controls_row = ft.Row(
            [network_dropdown, ft.Container(width=20), select_all_btn, clear_all_btn, bulk_edit_btn],
            spacing=10,
        )

        stats_row = ft.Row(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED, size=20, color=ft.Colors.BLUE_400),
                            ft.Text(f"Total accounts: {len(self.accounts)}", size=16, weight=ft.FontWeight.W_500),
                        ],
                        spacing=10,
                    ),
                    padding=ft.padding.only(left=15, right=15, top=10, bottom=10),
                    border_radius=20,
                    bgcolor=ft.Colors.GREY_900,
                )
            ],
            alignment=ft.MainAxisAlignment.START,
        )

        # Ширина колонки Value уменьшена до 280
        col_widths = {
            "select": 40,
            "id": 60,
            "value": 280,        # уменьшено
            "email": 280,
            "twitter": 250,
            "discord": 250,
            "actions": 160,
        }
        value_text_width = 240   # подогнано под новую ширину

        # Заголовок колонки "Value" с дропдауном внутри (центрирован)
        display_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option("key", "Private Key"),
                ft.dropdown.Option("address", "Address"),
            ],
            value=self.display_mode,
            width=col_widths["value"] - 20,
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
        )
        display_dropdown.on_select = self.on_display_mode_change
        value_header_cell = ft.Container(
            content=display_dropdown,
            width=col_widths["value"],
            alignment=ft.Alignment.CENTER,
            padding=ft.padding.only(left=8, right=8, top=4, bottom=4),
        )

        header_row = ft.Container(
            content=ft.Row(
                [
                    self.centered_header("", col_widths["select"]),
                    self.centered_header("ID", col_widths["id"]),
                    value_header_cell,
                    self.centered_header("Email", col_widths["email"]),
                    self.centered_header("Twitter", col_widths["twitter"]),
                    self.centered_header("Discord", col_widths["discord"]),
                    self.centered_header("Actions", col_widths["actions"]),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            border=ft.Border(
                top=ft.BorderSide(1, ft.Colors.GREY_800),
                left=ft.BorderSide(1, ft.Colors.GREY_800),
                right=ft.BorderSide(1, ft.Colors.GREY_800),
                bottom=ft.BorderSide(1, ft.Colors.GREY_800),
            ),
            bgcolor=ft.Colors.GREY_900,
        )

        filtered_accounts = self._filter_accounts()
        if filtered_accounts:
            rows_content = []
            for acc in filtered_accounts:
                cb = ft.Checkbox(
                    value=acc["id"] in self.selected_account_ids,
                    data=acc["id"],
                    on_change=self._on_select_account,
                )
                select_cell = ft.Container(content=cb, width=col_widths["select"], alignment=ft.Alignment.CENTER)

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

                display_value = self._get_account_display(acc, self.selected_network)
                display_short = display_value[:8] + "..." + display_value[-4:] if len(display_value) > 12 else display_value

                copy_btn = ft.IconButton(
                    icon=ft.Icons.CONTENT_COPY,
                    icon_size=16,
                    tooltip="Copy",
                    data=display_value,
                    on_click=self._copy_to_clipboard,
                    width=24,
                    height=24,
                    padding=0,
                )
                value_cell_content = ft.Row(
                    [
                        self.centered_cell(display_short, value_text_width, tooltip=display_value),
                        copy_btn,
                    ],
                    spacing=0,
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
                value_cell = ft.Container(content=value_cell_content, width=col_widths["value"], alignment=ft.Alignment.CENTER)

                row = ft.Container(
                    content=ft.Row(
                        [
                            select_cell,
                            self.centered_cell(str(acc.get("id", "")), col_widths["id"]),
                            value_cell,
                            self.centered_cell(acc.get("email", ""), col_widths["email"], tooltip=acc.get("email", "")),
                            self.centered_cell(acc.get("twitter_token", ""), col_widths["twitter"], tooltip=acc.get("twitter_token", "")),
                            self.centered_cell(acc.get("discord_token", ""), col_widths["discord"], tooltip=acc.get("discord_token", "")),
                            ft.Container(
                                content=ft.Row([edit_btn, delete_btn], spacing=2, alignment=ft.MainAxisAlignment.CENTER),
                                width=col_widths["actions"],
                                alignment=ft.Alignment.CENTER,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    border=ft.Border(
                        left=ft.BorderSide(1, ft.Colors.GREY_800),
                        right=ft.BorderSide(1, ft.Colors.GREY_800),
                        bottom=ft.BorderSide(1, ft.Colors.GREY_800),
                    ),
                )
                rows_content.append(row)

            body = ft.Container(
                content=ft.Column(rows_content, scroll=ft.ScrollMode.ALWAYS),
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

            table_content = ft.Column([header_row, body])

            table_container = ft.Container(
                content=ft.Row([table_content], scroll=ft.ScrollMode.ALWAYS),
                height=550,
                alignment=ft.Alignment.CENTER,
            )
        else:
            table_container = ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.ACCOUNT_BALANCE_OUTLINED, size=64, color=ft.Colors.GREY_600),
                        ft.Text("No wallets match the filter", size=20, color=ft.Colors.GREY_400),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=50,
                alignment=ft.Alignment.CENTER,
                height=400,
            )

        return ft.Container(
            content=ft.Column(
                [
                    header,
                    ft.Divider(height=20, color=ft.Colors.GREY_800),
                    controls_row,
                    ft.Container(height=10),
                    stats_row,
                    ft.Container(height=20),
                    table_container,
                ]
            ),
            padding=20,
        )

    def get_view(self) -> ft.Container:
        if self._cached_view is None or self._revision != self._last_revision:
            self._cached_view = self._build_view()
            self._last_revision = self._revision
        return self._cached_view

    def _on_select_account(self, e):
        acc_id = e.control.data
        if e.control.value:
            self.selected_account_ids.add(acc_id)
        else:
            self.selected_account_ids.discard(acc_id)
        self._increment_revision()
        self.update_content(self.get_view())

    def _select_all(self, e):
        filtered = self._filter_accounts()
        self.selected_account_ids = {acc["id"] for acc in filtered}
        self._increment_revision()
        self.update_content(self.get_view())

    def _clear_all(self, e):
        self.selected_account_ids.clear()
        self._increment_revision()
        self.update_content(self.get_view())

    def open_import_dialog(self, e: ft.ControlEvent = None):
        self.import_text_field = ft.TextField(
            label="Paste accounts data (one per line)",
            multiline=True,
            min_lines=10,
            max_lines=20,
            hint_text=(
                "Format: evm_key|sol_key|sui_key|aptos_key|btc_key|email|twitter_token|discord_token\n"
                "(backward compatible: evm_key|sol_key|email|twitter_token|discord_token)"
            ),
        )

        self.import_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Import wallets from text"),
            content=ft.Container(
                content=ft.Column(
                    [
                        self.import_text_field,
                        ft.Text("Each line should contain fields separated by '|'", size=12, color=ft.Colors.GREY_400),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                ),
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

    def close_import_dialog(self, e: ft.ControlEvent = None):
        if self.import_dialog:
            self.import_dialog.open = False
            self.page.update()

    def import_from_text(self, e: ft.ControlEvent = None):
        text = self.import_text_field.value
        if not text:
            return
        lines = text.strip().split("\n")
        new_accounts = []
        max_id = max([acc["id"] for acc in self.accounts], default=0)
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 5:
                evm, sol, email, twitter, discord = parts
                sui = aptos = btc = ""
            elif len(parts) >= 8:
                evm, sol, sui, aptos, btc, email, twitter, discord = parts[:8]
            else:
                print(f"Line {line_num}: expected 5 or 8 fields, got {len(parts)}")
                continue

            max_id += 1
            new_accounts.append(
                {
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
            )
        if new_accounts:
            self.accounts.extend(new_accounts)
            save_accounts(self.accounts)
            self._increment_revision()
            self.close_import_dialog()
            self.update_content(self.get_view())

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
        self.evm_field = ft.TextField(label="EVM Private Key", value=account.get("evm_private_key") if account else "", multiline=True, min_lines=1, max_lines=3)
        self.sol_field = ft.TextField(label="Solana Private Key", value=account.get("sol_private_key") if account else "", multiline=True, min_lines=1, max_lines=3)
        self.sui_field = ft.TextField(label="Sui Private Key", value=account.get("sui_private_key") if account else "", multiline=True, min_lines=1, max_lines=3)
        self.aptos_field = ft.TextField(label="Aptos Private Key", value=account.get("aptos_private_key") if account else "", multiline=True, min_lines=1, max_lines=3)
        self.btc_field = ft.TextField(label="Bitcoin Private Key (WIF)", value=account.get("btc_private_key") if account else "", multiline=True, min_lines=1, max_lines=3)
        self.email_field = ft.TextField(label="Email (log:pass)", value=account.get("email") if account else "", multiline=True, min_lines=1, max_lines=3)
        self.twitter_field = ft.TextField(label="Twitter token", value=account.get("twitter_token") if account else "", multiline=True, min_lines=1, max_lines=3)
        self.discord_field = ft.TextField(label="Discord token", value=account.get("discord_token") if account else "", multiline=True, min_lines=1, max_lines=3)

        self.dialog_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit account" if account else "Add new account"),
            content=ft.Container(
                content=ft.Column(
                    [
                        self.evm_field,
                        self.sol_field,
                        self.sui_field,
                        self.aptos_field,
                        self.btc_field,
                        self.email_field,
                        self.twitter_field,
                        self.discord_field,
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    height=500,
                ),
                width=550,
            ),
            actions=[
                ft.TextButton("Save", on_click=self.save_account),
                ft.TextButton("Cancel", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(self.dialog_modal)

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
                    acc.update(
                        {
                            "evm_private_key": self.evm_field.value or "",
                            "sol_private_key": self.sol_field.value or "",
                            "sui_private_key": self.sui_field.value or "",
                            "aptos_private_key": self.aptos_field.value or "",
                            "btc_private_key": self.btc_field.value or "",
                            "email": self.email_field.value or "",
                            "twitter_token": self.twitter_field.value or "",
                            "discord_token": self.discord_field.value or "",
                        }
                    )
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
        self.selected_account_ids.discard(account_id)
        save_accounts(self.accounts)
        self._increment_revision()
        self.update_content(self.get_view())

    def delete_account(self, e: ft.ControlEvent):
        account_id = e.control.data
        self._confirm_delete(account_id)
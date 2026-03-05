import flet as ft
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


DATA_DIR = Path("data")
EXPENSES_FILE = DATA_DIR / "expenses.json"

CATEGORIES = ["Proxy", "Captcha", "Gas", "Software", "Other"]

SCOPE_GLOBAL = "global"
SCOPE_PROJECT = "project"

def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)

def load_expenses() -> List[Dict[str, Any]]:
    ensure_data_dir()
    if not EXPENSES_FILE.exists():
        with open(EXPENSES_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []
    with open(EXPENSES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_expenses(expenses: List[Dict[str, Any]]):
    ensure_data_dir()
    with open(EXPENSES_FILE, 'w', encoding='utf-8') as f:
        json.dump(expenses, f, indent=4, ensure_ascii=False)


class ExpensesManager:
    def __init__(self, page: ft.Page, update_content_callback, accounts_manager, projects_manager):
        self.page = page
        self.update_content = update_content_callback
        self.accounts_manager = accounts_manager
        self.projects_manager = projects_manager
        self.expenses = load_expenses()

        self.filter_project_dropdown = None
        self.filter_account_dropdown = None

        # Поля диалога
        self.scope_radio = None
        self.date_field = None
        self.project_dropdown = None
        self.account_dropdown = None
        self.category_dropdown = None
        self.amount_field = None
        self.desc_field = None
        self.dialog_modal = None
        self.editing_expense_id = None

    def get_view(self) -> ft.Container:
        # Заголовок и кнопка добавления
        header = ft.Row([
            ft.Text("Expenses management", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.ElevatedButton(
                "Add expense",
                icon=ft.Icons.ADD,
                on_click=self.open_add_expense_dialog,
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.BLUE_600
                )
            ),
        ])

        # Фильтры
        self.filter_project_dropdown = ft.Dropdown(
            label="Filter by Project",
            options=[ft.dropdown.Option("all", "All Projects")] + self._get_project_options(),
            value="all",
            width=200,
        )
        self.filter_project_dropdown.on_change = self.apply_filters

        self.filter_account_dropdown = ft.Dropdown(
            label="Filter by Account",
            options=[ft.dropdown.Option("all", "All Accounts")] + self._get_account_options(),
            value="all",
            width=200,
        )
        self.filter_account_dropdown.on_change = self.apply_filters

        filters_row = ft.Row([self.filter_project_dropdown, self.filter_account_dropdown], spacing=10)

        # Таблица расходов
        expenses_table = self._create_expenses_table()

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=20, color=ft.Colors.GREY_800),
                filters_row,
                ft.Container(height=20),
                ft.Text("Expenses list", size=18, weight=ft.FontWeight.BOLD),
                expenses_table
            ]),
            padding=20
        )

    def _get_project_options(self) -> List[ft.dropdown.Option]:
        options = []
        for proj in self.projects_manager.projects:
            options.append(ft.dropdown.Option(
                key=str(proj["id"]),
                text=f"{proj['id']}: {proj.get('name', 'Unknown')[:30]}"
            ))
        return options

    def _get_account_options(self) -> List[ft.dropdown.Option]:
        options = []
        for acc in self.accounts_manager.accounts:
            key = acc.get("evm_private_key", "")
            if key:
                short_key = key[:8] + "..." + key[-4:] if len(key) > 12 else key
            else:
                short_key = "No key"
            options.append(ft.dropdown.Option(
                key=str(acc["id"]),
                text=f"{acc['id']}: {short_key}"
            ))
        return options

    def _create_expenses_table(self) -> ft.Container:
        filtered = self._filtered_expenses()

        if not filtered:
            return ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.RECEIPT_OUTLINED, size=64, color=ft.Colors.GREY_600),
                    ft.Text("No expenses yet", size=20, color=ft.Colors.GREY_400),
                    ft.Text("Click 'Add expense' to record your first expense", color=ft.Colors.GREY_500),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=50,
                alignment=ft.Alignment.CENTER,
                height=400,
            )

        rows = []
        total_amount = 0.0
        for exp in filtered:
            total_amount += exp.get("amount", 0)

            edit_btn = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.BLUE_400,
                tooltip="Edit expense",
                data=exp["id"],
                on_click=self.open_edit_expense_dialog
            )
            delete_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                tooltip="Delete expense",
                data=exp["id"],
                on_click=self.delete_expense
            )

            # Определяем, что отображать в колонках Project и Account
            if exp.get("project_id"):
                project_name = self._get_project_name(exp["project_id"])
                if exp.get("account_id"):
                    account_text = self._get_account_label(exp["account_id"])
                else:
                    account_text = "All accounts"
            else:
                project_name = "Global"
                account_text = "-"

            date_text = ft.Text(exp.get("date", ""), size=12)
            project_text_widget = ft.Text(project_name, size=12, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, width=120)
            account_text_widget = ft.Text(account_text, size=12, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, width=120)
            category_text = ft.Text(exp.get("category", ""), size=12)
            amount_text = ft.Text(f"${exp.get('amount', 0):.2f}", size=12)
            desc_text = ft.Text(exp.get("description", ""), size=12, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, width=150)

            row = ft.DataRow(
                cells=[
                    ft.DataCell(date_text),
                    ft.DataCell(project_text_widget),
                    ft.DataCell(account_text_widget),
                    ft.DataCell(category_text),
                    ft.DataCell(amount_text),
                    ft.DataCell(desc_text),
                    ft.DataCell(ft.Row([edit_btn, delete_btn], spacing=5)),
                ]
            )
            rows.append(row)

        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Date", size=12)),
                ft.DataColumn(ft.Text("Project", size=12)),
                ft.DataColumn(ft.Text("Account", size=12)),
                ft.DataColumn(ft.Text("Category", size=12)),
                ft.DataColumn(ft.Text("Amount", size=12)),
                ft.DataColumn(ft.Text("Description", size=12)),
                ft.DataColumn(ft.Text("Actions", size=12)),
            ],
            rows=rows,
            border=ft.Border.all(1, ft.Colors.GREY_800),
            vertical_lines=ft.BorderSide(1, ft.Colors.GREY_800),
            horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_800),
            column_spacing=15,
        )

        total_row = ft.Container(
            content=ft.Row([
                ft.Text("Total: ", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(f"${total_amount:.2f}", size=16, color=ft.Colors.GREEN_400),
            ], alignment=ft.MainAxisAlignment.END),
            padding=10,
        )

        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([table], scroll=ft.ScrollMode.ALWAYS),
                    height=400,
                ),
                total_row,
            ]),
        )

    def _filtered_expenses(self) -> List[Dict[str, Any]]:
        project_filter = self.filter_project_dropdown.value if self.filter_project_dropdown else "all"
        account_filter = self.filter_account_dropdown.value if self.filter_account_dropdown else "all"

        filtered = []
        for exp in self.expenses:
            exp_project = str(exp.get("project_id")) if exp.get("project_id") else None
            exp_account = str(exp.get("account_id")) if exp.get("account_id") else None

            # Фильтр по проекту
            if project_filter != "all":
                if exp_project is None:
                    pass
                elif exp_project != project_filter:
                    continue

            # Фильтр по аккаунту
            if account_filter != "all":
                if exp_account is None:
                    continue
                elif exp_account != account_filter:
                    continue

            filtered.append(exp)
        return filtered

    def _get_project_name(self, project_id: Optional[int]) -> str:
        if project_id is None:
            return "Global"
        for proj in self.projects_manager.projects:
            if proj["id"] == project_id:
                return proj.get("name", "Unknown")
        return f"ID {project_id} (deleted)"

    def _get_account_label(self, account_id: Optional[int]) -> str:
        if account_id is None:
            return "All accounts"
        for acc in self.accounts_manager.accounts:
            if acc["id"] == account_id:
                key = acc.get("evm_private_key", "")
                if key:
                    short_key = key[:8] + "..." + key[-4:] if len(key) > 12 else key
                else:
                    short_key = "No key"
                return f"{acc['id']}: {short_key}"
        return f"ID {account_id} (deleted)"

    def apply_filters(self, e):
        self.update_content(self.get_view())

    def open_add_expense_dialog(self, e: ft.ControlEvent = None):
        self.editing_expense_id = None
        self._show_expense_dialog()

    def open_edit_expense_dialog(self, e: ft.ControlEvent):
        expense_id = e.control.data
        self.editing_expense_id = expense_id
        expense = next((exp for exp in self.expenses if exp["id"] == expense_id), None)
        if expense:
            self._show_expense_dialog(expense)

    def _show_expense_dialog(self, expense: Optional[Dict] = None):
        initial_scope = expense.get("scope", SCOPE_PROJECT) if expense else SCOPE_PROJECT

        # Две радиокнопки: Project expense и Global expense
        self.scope_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value=SCOPE_PROJECT, label="Project expense"),
                ft.Radio(value=SCOPE_GLOBAL, label="Global expense"),
            ]),
            value=initial_scope
        )
        self.scope_radio.on_change = self.on_scope_change

        self.date_field = ft.TextField(
            label="Date (YYYY-MM-DD)",
            value=expense.get("date") if expense else "",
            hint_text="2025-03-05",
        )

        self.category_dropdown = ft.Dropdown(
            label="Category",
            options=[ft.dropdown.Option(cat, cat) for cat in CATEGORIES],
            value=expense.get("category") if expense else CATEGORIES[0],
        )

        self.amount_field = ft.TextField(
            label="Amount (USD)",
            value=str(expense.get("amount", "")) if expense else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="0.00",
        )

        self.desc_field = ft.TextField(
            label="Description",
            value=expense.get("description") if expense else "",
            multiline=True,
            min_lines=2,
            max_lines=4,
        )

        # Dropdown для проекта и аккаунта
        self.project_dropdown = ft.Dropdown(
            label="Project",
            options=[ft.dropdown.Option("", "Select project")] + self._get_project_options(),
            value=str(expense.get("project_id")) if expense and expense.get("project_id") else "",
        )
        self.account_dropdown = ft.Dropdown(
            label="Account (optional)",
            options=[ft.dropdown.Option("", "All accounts")] + self._get_account_options(),
            value=str(expense.get("account_id")) if expense and expense.get("account_id") else "",
        )

        # Настраиваем enabled/disabled в зависимости от scope
        self._update_fields_for_scope(initial_scope)

        self.dialog_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Expense" if expense else "Add New Expense"),
            content=ft.Container(
                content=ft.Column([
                    self.scope_radio,
                    ft.Divider(height=10, color=ft.Colors.GREY_800),
                    self.date_field,
                    self.project_dropdown,
                    self.account_dropdown,
                    self.category_dropdown,
                    self.amount_field,
                    self.desc_field,
                ], scroll=ft.ScrollMode.AUTO, height=550),
                width=500,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog),
                ft.ElevatedButton("Save", on_click=self.save_expense),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(self.dialog_modal)

    def on_scope_change(self, e):
        self._update_fields_for_scope(self.scope_radio.value)
        self.page.update()

    def _update_fields_for_scope(self, scope: str):
        if scope == SCOPE_PROJECT:
            self.project_dropdown.disabled = False
            self.account_dropdown.disabled = False
        else:  # global
            self.project_dropdown.disabled = True
            self.account_dropdown.disabled = True
            # Сбрасываем значения
            self.project_dropdown.value = ""
            self.account_dropdown.value = ""

    def close_dialog(self, e: ft.ControlEvent = None):
        self.dialog_modal.open = False
        self.page.update()

    def save_expense(self, e: ft.ControlEvent = None):
        if not self.date_field.value or not self.amount_field.value:
            return

        try:
            amount = float(self.amount_field.value)
        except ValueError:
            amount = 0.0

        scope = self.scope_radio.value

        expense_data = {
            "id": self.editing_expense_id if self.editing_expense_id else 0,
            "date": self.date_field.value,
            "scope": scope,
            "category": self.category_dropdown.value,
            "amount": amount,
            "description": self.desc_field.value,
        }

        if scope == SCOPE_PROJECT:
            if not self.project_dropdown.value:
                # Проект обязателен
                return
            expense_data["project_id"] = int(self.project_dropdown.value)
            expense_data["account_id"] = int(self.account_dropdown.value) if self.account_dropdown.value else None
        else:  # global
            expense_data["project_id"] = None
            expense_data["account_id"] = None

        if self.editing_expense_id is None:
            new_id = max([exp["id"] for exp in self.expenses], default=0) + 1
            expense_data["id"] = new_id
            self.expenses.append(expense_data)
        else:
            for i, exp in enumerate(self.expenses):
                if exp["id"] == self.editing_expense_id:
                    expense_data["id"] = self.editing_expense_id
                    self.expenses[i] = expense_data
                    break

        save_expenses(self.expenses)
        self.close_dialog()
        self.update_content(self.get_view())

    def delete_expense(self, e: ft.ControlEvent):
        expense_id = e.control.data
        self.expenses = [exp for exp in self.expenses if exp["id"] != expense_id]
        save_expenses(self.expenses)
        self.update_content(self.get_view())
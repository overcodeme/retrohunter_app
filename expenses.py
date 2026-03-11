import flet as ft
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


DATA_DIR = Path("data")
EXPENSES_FILE = DATA_DIR / "expenses.json"

CATEGORIES = ["Proxy", "Captcha", "Gas", "Software", "Other"]

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
        self.date_field = None
        self.project_dropdown = None
        self.account_dropdown = None
        self.category_dropdown = None
        self.amount_field = None
        self.desc_field = None
        self.dialog_modal = None
        self.editing_expense_id = None

    # ----- Вспомогательные методы для кастомной таблицы -----
    @staticmethod
    def centered_header(text: str, width: int) -> ft.Container:
        """Ячейка заголовка с центрированием (шрифт 17)"""
        return ft.Container(
            content=ft.Text(
                text,
                size=17,                           # увеличено с 16 до 17
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
    def centered_cell(text: str, width: int, tooltip: str = "") -> ft.Container:
        """Ячейка данных с центрированием (шрифт 16)"""
        return ft.Container(
            content=ft.Text(
                text,
                size=16,                           # увеличено с 15 до 16
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

    # ----- Основное представление -----
    def get_view(self) -> ft.Container:
        header = ft.Row([
            ft.Text("Expenses list", size=24, weight=ft.FontWeight.BOLD),
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

        # Получаем отфильтрованные расходы и вычисляем итог
        filtered = self._filtered_expenses()
        total_amount = sum(exp.get("amount", 0) for exp in filtered)

        # Контейнер с итоговой суммой
        total_container = ft.Container(
            content=ft.Row([
                ft.Text("Total:", size=17, weight=ft.FontWeight.W_500),
                ft.Text(f"${total_amount:.2f}", size=19, weight=ft.FontWeight.W_500, color=ft.Colors.GREEN_400),
            ], spacing=5, alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=20, right=20, top=12, bottom=12),
            bgcolor=ft.Colors.GREY_900,
            border_radius=30,
            margin=ft.margin.only(right=10),
        )

        # Верхняя строка: фильтры слева, итог справа
        top_row = ft.Row([
            filters_row,
            ft.Container(expand=True),
            total_container,
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # Таблица расходов
        expenses_table = self._create_expenses_table(filtered)

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=20, color=ft.Colors.GREY_800),
                top_row,
                ft.Container(height=20),
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

    def _create_expenses_table(self, filtered: List[Dict[str, Any]]) -> ft.Container:
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

        # Ширины колонок (расширена колонка Description)
        col_widths = {
            "date": 130,
            "project": 220,
            "account": 220,
            "category": 130,
            "amount": 110,
            "description": 300,          # увеличено с 250 до 300
            "actions": 100,
        }

        # Заголовок таблицы
        header_row = ft.Container(
            content=ft.Row([
                self.centered_header("Date", col_widths["date"]),
                self.centered_header("Project", col_widths["project"]),
                self.centered_header("Account", col_widths["account"]),
                self.centered_header("Category", col_widths["category"]),
                self.centered_header("Amount", col_widths["amount"]),
                self.centered_header("Description", col_widths["description"]),
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

        rows_content = []
        for exp in filtered:
            edit_btn = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.BLUE_400,
                tooltip="Edit expense",
                data=exp["id"],
                on_click=self.open_edit_expense_dialog,
                width=32,
                height=32,
                padding=0,
                icon_size=20,
            )
            delete_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                tooltip="Delete expense",
                data=exp["id"],
                on_click=self.delete_expense,
                width=32,
                height=32,
                padding=0,
                icon_size=20,
            )

            # Определяем текст для проекта и аккаунта
            if exp.get("project_id"):
                project_name = self._get_project_name(exp["project_id"])
                if exp.get("account_id"):
                    account_text = self._get_account_label(exp["account_id"])
                else:
                    account_text = "-"
            else:
                project_name = "Global"
                account_text = "-"

            date_text = exp.get("date", "")
            category = exp.get("category", "")
            amount = exp.get("amount", 0)
            amount_str = f"${amount:.2f}"
            description = exp.get("description", "")

            row = ft.Container(
                content=ft.Row([
                    self.centered_cell(date_text, col_widths["date"]),
                    self.centered_cell(project_name, col_widths["project"], tooltip=project_name),
                    self.centered_cell(account_text, col_widths["account"], tooltip=account_text),
                    self.centered_cell(category, col_widths["category"]),
                    self.centered_cell(amount_str, col_widths["amount"]),
                    self.centered_cell(description, col_widths["description"], tooltip=description),
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

        # Тело таблицы с вертикальной прокруткой
        body = ft.Container(
            content=ft.Column(
                rows_content,
                scroll=ft.ScrollMode.ALWAYS,
            ),
            height=450,
            border=ft.Border(
                left=ft.BorderSide(1, ft.Colors.GREY_800),
                right=ft.BorderSide(1, ft.Colors.GREY_800),
                bottom=ft.BorderSide(1, ft.Colors.GREY_800),
            ),
        )

        # Объединяем заголовок и тело
        table_content = ft.Column([
            header_row,
            body,
        ])

        # Внешний контейнер с горизонтальной прокруткой
        table_container = ft.Container(
            content=ft.Row(
                [table_content],
                scroll=ft.ScrollMode.ALWAYS,
            ),
            height=500,
            alignment=ft.Alignment.CENTER,
        )

        return table_container

    def _filtered_expenses(self) -> List[Dict[str, Any]]:
        project_filter = self.filter_project_dropdown.value if self.filter_project_dropdown else "all"
        account_filter = self.filter_account_dropdown.value if self.filter_account_dropdown else "all"

        filtered = []
        for exp in self.expenses:
            exp_project = str(exp.get("project_id")) if exp.get("project_id") else None
            exp_account = str(exp.get("account_id")) if exp.get("account_id") else None

            if project_filter != "all":
                if exp_project is None:
                    # глобальные расходы показываем всегда
                    pass
                elif exp_project != project_filter:
                    continue

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
            return "-"
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

    # ----- Диалог добавления/редактирования -----
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

        # Выпадающий список проектов + пустая опция для глобальных расходов
        self.project_dropdown = ft.Dropdown(
            label="Project (leave empty for global expense)",
            options=[ft.dropdown.Option("", "-- Global --")] + self._get_project_options(),
            value=str(expense.get("project_id")) if expense and expense.get("project_id") else "",
        )
        # on_change назначаем отдельно
        self.project_dropdown.on_change = self.on_project_change

        # Выпадающий список аккаунтов
        self.account_dropdown = ft.Dropdown(
            label="Account (optional)",
            options=[ft.dropdown.Option("", "-- All accounts --")] + self._get_account_options(),
            value=str(expense.get("account_id")) if expense and expense.get("account_id") else "",
        )

        # Устанавливаем начальное состояние аккаунта
        self._update_account_state()

        self.dialog_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Expense" if expense else "Add New Expense"),
            content=ft.Container(
                content=ft.Column([
                    self.date_field,
                    self.project_dropdown,
                    self.account_dropdown,
                    self.category_dropdown,
                    self.amount_field,
                    self.desc_field,
                ], scroll=ft.ScrollMode.AUTO, height=500),
                width=500,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog),
                ft.ElevatedButton("Save", on_click=self.save_expense),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(self.dialog_modal)

    def on_project_change(self, e):
        """Обработчик изменения выбранного проекта – активирует/деактивирует поле аккаунта"""
        self._update_account_state()
        self.page.update()

    def _update_account_state(self):
        """Включает поле аккаунта, если выбран проект, иначе отключает и сбрасывает"""
        if self.project_dropdown.value:
            self.account_dropdown.disabled = False
        else:
            self.account_dropdown.disabled = True
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

        expense_data = {
            "id": self.editing_expense_id if self.editing_expense_id else 0,
            "date": self.date_field.value,
            "category": self.category_dropdown.value,
            "amount": amount,
            "description": self.desc_field.value,
        }

        if self.project_dropdown.value:
            expense_data["project_id"] = int(self.project_dropdown.value)
            if self.account_dropdown.value:
                expense_data["account_id"] = int(self.account_dropdown.value)
            else:
                expense_data["account_id"] = None
        else:
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
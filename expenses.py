import flet as ft
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


DATA_DIR = Path("data")
EXPENSES_FILE = DATA_DIR / "expenses.json"

CATEGORIES = ["Proxy", "Captcha", "Gas", "Software", "Other"]

# Типы операций
TYPE_EXPENSE = "expense"
TYPE_INCOME = "income"

# Сети
NETWORK_EVM = "evm"
NETWORK_SOLANA = "solana"

def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)

def load_expenses() -> List[Dict[str, Any]]:
    ensure_data_dir()
    if not EXPENSES_FILE.exists():
        with open(EXPENSES_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []
    with open(EXPENSES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Миграция старых данных: если есть account_id (int) превращаем в список
        for exp in data:
            if "account_id" in exp and exp["account_id"] is not None:
                exp["account_ids"] = [exp["account_id"]]
                del exp["account_id"]
            elif "account_ids" not in exp:
                exp["account_ids"] = []
            # Добавляем поле network, если нет
            if "network" not in exp:
                exp["network"] = NETWORK_EVM  # по умолчанию EVM
        return data

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
        self.type_radio = None
        self.network_radio = None
        self.date_field = None
        self.project_dropdown = None
        self.search_field = None
        self.accounts_list = None  # Column с чекбоксами
        self.category_dropdown = None
        self.amount_field = None
        self.desc_field = None
        self.dialog_modal = None
        self.editing_expense_id = None
        self.current_expense_accounts = []  # список ID выбранных аккаунтов при редактировании
        self.current_network = NETWORK_EVM

    # ----- Вспомогательные методы для кастомной таблицы -----
    @staticmethod
    def centered_header(text: str, width: int) -> ft.Container:
        """Ячейка заголовка с центрированием"""
        return ft.Container(
            content=ft.Text(
                text,
                size=17,
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
        """Ячейка данных с центрированием (одна строка + подсказка)"""
        return ft.Container(
            content=ft.Text(
                text,
                size=16,
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

    @staticmethod
    def amount_cell(amount: float, type_: str, width: int) -> ft.Container:
        """Ячейка суммы с цветом в зависимости от типа (expense/income)"""
        color = ft.Colors.RED_400 if type_ == TYPE_EXPENSE else ft.Colors.GREEN_400
        sign = "-" if type_ == TYPE_EXPENSE else "+"
        text = f"{sign}${abs(amount):.2f}"
        return ft.Container(
            content=ft.Text(
                text,
                size=16,
                selectable=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                text_align=ft.TextAlign.CENTER,
                color=color,
            ),
            width=width,
            alignment=ft.Alignment.CENTER,
            padding=ft.padding.only(left=8, right=8, top=4, bottom=4),
        )

    def _format_accounts(self, account_ids: List[int], network: str) -> str:
        """Формирует строку для отображения списка аккаунтов в таблице"""
        if not account_ids:
            return "-"
        count = len(account_ids)
        network_label = "EVM" if network == NETWORK_EVM else "Solana"
        return f"{count} {network_label}"

    def _get_accounts_tooltip(self, account_ids: List[int], network: str) -> str:
        """Формирует всплывающую подсказку со списком ID аккаунтов и сетью"""
        if not account_ids:
            return ""
        network_label = "EVM" if network == NETWORK_EVM else "Solana"
        ids_str = ", ".join(str(id) for id in account_ids)
        return f"{network_label}: {ids_str}"

    def _get_account_display_key(self, acc: Dict, network: str) -> str:
        """Возвращает сокращённый ключ для отображения (первые 4 + ... + последние 4)"""
        if network == NETWORK_EVM:
            key = acc.get("evm_private_key", "")
        else:
            key = acc.get("sol_private_key", "")
        if key and len(key) > 8:
            return key[:4] + "..." + key[-4:]
        elif key:
            return key
        else:
            return "No key"

    # ----- Основное представление -----
    def get_view(self) -> ft.Container:
        header = ft.Row([
            ft.Text("Expenses & Incomes", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.ElevatedButton(
                "Add operation",
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

        # Получаем отфильтрованные операции
        filtered = self._filtered_expenses()

        # Суммируем отдельно расходы и доходы
        total_expenses = sum(exp.get("amount", 0) for exp in filtered if exp.get("type", TYPE_EXPENSE) == TYPE_EXPENSE)
        total_incomes = sum(exp.get("amount", 0) for exp in filtered if exp.get("type", TYPE_EXPENSE) == TYPE_INCOME)

        # Контейнеры с итогами
        expenses_container = ft.Container(
            content=ft.Row([
                ft.Text("Expenses:", size=17, weight=ft.FontWeight.W_500),
                ft.Text(f"-${total_expenses:.2f}", size=19, weight=ft.FontWeight.W_500, color=ft.Colors.RED_400),
            ], spacing=5, alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=20, right=20, top=12, bottom=12),
            bgcolor=ft.Colors.GREY_900,
            border_radius=30,
        )

        incomes_container = ft.Container(
            content=ft.Row([
                ft.Text("Incomes:", size=17, weight=ft.FontWeight.W_500),
                ft.Text(f"+${total_incomes:.2f}", size=19, weight=ft.FontWeight.W_500, color=ft.Colors.GREEN_400),
            ], spacing=5, alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(left=20, right=20, top=12, bottom=12),
            bgcolor=ft.Colors.GREY_900,
            border_radius=30,
        )

        # Строка с итогами
        totals_row = ft.Row([
            expenses_container,
            ft.Container(width=10),
            incomes_container,
        ], alignment=ft.MainAxisAlignment.END)

        # Верхняя строка: фильтры слева, итоги справа
        top_row = ft.Row([
            filters_row,
            ft.Container(expand=True),
            totals_row,
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # Таблица операций
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
        # Используется только для фильтра по аккаунту (одиночный выбор)
        options = []
        for acc in self.accounts_manager.accounts:
            # Показываем ID и сокращённый EVM ключ (можно и Solana, но для фильтра не важно)
            key = acc.get("evm_private_key", "")
            if key:
                short_key = key[:4] + "..." + key[-4:] if len(key) > 8 else key
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
                    ft.Text("No operations yet", size=20, color=ft.Colors.GREY_400),
                    ft.Text("Click 'Add operation' to record your first operation", color=ft.Colors.GREY_500),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=50,
                alignment=ft.Alignment.CENTER,
                height=400,
            )

        # Ширины колонок
        col_widths = {
            "date": 130,
            "type": 80,
            "project": 220,
            "accounts": 200,
            "category": 130,
            "amount": 120,
            "description": 300,
            "actions": 100,
        }

        # Заголовок таблицы
        header_row = ft.Container(
            content=ft.Row([
                self.centered_header("Date", col_widths["date"]),
                self.centered_header("Type", col_widths["type"]),
                self.centered_header("Project", col_widths["project"]),
                self.centered_header("Accounts", col_widths["accounts"]),
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
                tooltip="Edit",
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
                tooltip="Delete",
                data=exp["id"],
                on_click=self.delete_expense,
                width=32,
                height=32,
                padding=0,
                icon_size=20,
            )

            # Определяем текст для проекта и аккаунтов
            if exp.get("project_id"):
                project_name = self._get_project_name(exp["project_id"])
            else:
                project_name = "Global"

            account_ids = exp.get("account_ids", [])
            network = exp.get("network", NETWORK_EVM)
            accounts_text = self._format_accounts(account_ids, network)
            accounts_tooltip = self._get_accounts_tooltip(account_ids, network)

            date_text = exp.get("date", "")
            op_type = exp.get("type", TYPE_EXPENSE)
            type_text = "Expense" if op_type == TYPE_EXPENSE else "Income"
            category = exp.get("category", "")
            amount = exp.get("amount", 0)
            description = exp.get("description", "")

            row = ft.Container(
                content=ft.Row([
                    self.centered_cell(date_text, col_widths["date"]),
                    self.centered_cell(type_text, col_widths["type"]),
                    self.centered_cell(project_name, col_widths["project"], tooltip=project_name),
                    self.centered_cell(accounts_text, col_widths["accounts"], tooltip=accounts_tooltip),
                    self.centered_cell(category, col_widths["category"]),
                    self.amount_cell(amount, op_type, col_widths["amount"]),
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
            exp_accounts = exp.get("account_ids", [])

            # Фильтр по проекту
            if project_filter != "all":
                if exp_project is None:
                    # глобальные показываем всегда
                    pass
                elif exp_project != project_filter:
                    continue

            # Фильтр по аккаунту (если выбран конкретный аккаунт)
            if account_filter != "all":
                if not exp_accounts:
                    continue
                if int(account_filter) not in exp_accounts:
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

    def apply_filters(self, e):
        self.update_content(self.get_view())

    # ---------- ДИАЛОГ ДОБАВЛЕНИЯ/РЕДАКТИРОВАНИЯ ----------
    def open_add_expense_dialog(self, e: ft.ControlEvent = None):
        self.editing_expense_id = None
        self.current_expense_accounts = []
        self.current_network = NETWORK_EVM
        self._show_expense_dialog()

    def open_edit_expense_dialog(self, e: ft.ControlEvent):
        expense_id = e.control.data
        self.editing_expense_id = expense_id
        expense = next((exp for exp in self.expenses if exp["id"] == expense_id), None)
        if expense:
            self.current_expense_accounts = expense.get("account_ids", [])
            self.current_network = expense.get("network", NETWORK_EVM)
            self._show_expense_dialog(expense)

    def _show_expense_dialog(self, expense: Optional[Dict] = None):
        # Радиокнопки для выбора типа (расход/доход)
        self.type_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value=TYPE_EXPENSE, label="Expense", fill_color=ft.Colors.RED_400),
                ft.Radio(value=TYPE_INCOME, label="Income", fill_color=ft.Colors.GREEN_400),
            ]),
            value=expense.get("type") if expense else TYPE_EXPENSE,
        )

        # Радиокнопки для выбора сети (EVM/Solana)
        self.network_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value=NETWORK_EVM, label="EVM", fill_color=ft.Colors.BLUE_400),
                ft.Radio(value=NETWORK_SOLANA, label="Solana", fill_color=ft.Colors.PURPLE_400),
            ]),
            value=self.current_network,
            on_change=self.on_network_change,
        )

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

        # Выпадающий список проектов + пустая опция для глобальных операций
        self.project_dropdown = ft.Dropdown(
            label="Project (leave empty for global)",
            options=[ft.dropdown.Option("", "-- Global --")] + self._get_project_options(),
            value=str(expense.get("project_id")) if expense and expense.get("project_id") else "",
        )
        self.project_dropdown.on_change = self.on_project_change

        # Поиск аккаунтов
        self.search_field = ft.TextField(
            label="Search accounts",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self.filter_accounts,
            hint_text="Type to filter by private key or email",
        )

        # Кнопки управления выделением
        select_all_btn = ft.TextButton("Select All", on_click=self.select_all_accounts)
        clear_all_btn = ft.TextButton("Clear All", on_click=self.clear_all_accounts)

        # Контейнер для списка аккаунтов
        self.accounts_list = ft.Column(scroll=ft.ScrollMode.AUTO, height=200)
        self._build_accounts_list()

        # Диалог
        self.dialog_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit operation" if expense else "Add new operation"),
            content=ft.Container(
                content=ft.Column([
                    self.type_radio,
                    self.network_radio,
                    ft.Divider(height=10, color=ft.Colors.GREY_800),
                    self.date_field,
                    self.project_dropdown,
                    ft.Divider(height=10, color=ft.Colors.GREY_800),
                    ft.Text("Select accounts (multiple):", size=14, weight=ft.FontWeight.BOLD),
                    ft.Row([select_all_btn, clear_all_btn], alignment=ft.MainAxisAlignment.START),
                    self.search_field,
                    ft.Container(
                        content=self.accounts_list,
                        border=ft.Border.all(1, ft.Colors.GREY_800),
                        border_radius=5,
                        padding=10,
                        height=220,
                    ),
                    self.category_dropdown,
                    self.amount_field,
                    self.desc_field,
                ], scroll=ft.ScrollMode.AUTO, height=700),
                width=600,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog),
                ft.ElevatedButton("Save", on_click=self.save_expense),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(self.dialog_modal)

    def _build_accounts_list(self, filter_text: str = ""):
        if not self.accounts_manager or not self.accounts_manager.accounts:
            self.accounts_list.controls = [ft.Text("No accounts available", color=ft.Colors.GREY_400)]
            return

        checkboxes = []
        filter_text = filter_text.lower()
        network = self.network_radio.value if self.network_radio else self.current_network

        for acc in self.accounts_manager.accounts:
            # Проверяем наличие ключа в выбранной сети
            if network == NETWORK_EVM:
                key = acc.get("evm_private_key", "")
                addr = acc.get("evm_address")
            else:
                key = acc.get("sol_private_key", "")
                addr = acc.get("solana_address")
            if not key:
                continue  # нет ключа в этой сети

            # Строка для поиска (включаем ID, адрес, email)
            searchable_string = f"id:{acc['id']} {addr or ''} {acc.get('email', '')}".lower()
            if filter_text and filter_text not in searchable_string:
                continue

            # Формируем метку: сеть + ID + сокращённый адрес (или ключ, если нет адреса)
            network_label = "EVM" if network == NETWORK_EVM else "Solana"
            if addr:
                display = addr[:4] + "..." + addr[-4:]
            else:
                # fallback на ключ (не рекомендуется, но для совместимости)
                display = key[:4] + "..." + key[-4:] if len(key) > 8 else key
            label = f"{network_label} {acc['id']} ({display})"
            cb = ft.Checkbox(
                label=label,
                value=acc["id"] in self.current_expense_accounts,
                data=acc["id"],
            )
            checkboxes.append(cb)

        self.accounts_list.controls = checkboxes if checkboxes else [ft.Text("No matching accounts", color=ft.Colors.GREY_400)]
        self.page.update()
    def on_network_change(self, e):
        """Обработчик смены сети – перестраивает список аккаунтов"""
        self.current_network = self.network_radio.value
        self._build_accounts_list(self.search_field.value if self.search_field else "")
        self.page.update()

    def filter_accounts(self, e):
        self._build_accounts_list(self.search_field.value)

    def select_all_accounts(self, e):
        for cb in self.accounts_list.controls:
            if isinstance(cb, ft.Checkbox):
                cb.value = True
        self.page.update()

    def clear_all_accounts(self, e):
        for cb in self.accounts_list.controls:
            if isinstance(cb, ft.Checkbox):
                cb.value = False
        self.page.update()

    def on_project_change(self, e):
        # При изменении проекта можно ничего не делать, но можно обновить список аккаунтов, если нужно
        self.page.update()

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

        # Получаем тип операции и сеть
        op_type = self.type_radio.value
        network = self.network_radio.value

        # Собираем выбранные аккаунты
        selected_accounts = [
            cb.data for cb in self.accounts_list.controls
            if isinstance(cb, ft.Checkbox) and cb.value
        ]

        expense_data = {
            "id": self.editing_expense_id if self.editing_expense_id else 0,
            "date": self.date_field.value,
            "type": op_type,
            "network": network,
            "category": self.category_dropdown.value,
            "amount": amount,
            "description": self.desc_field.value,
            "account_ids": selected_accounts,
        }

        if self.project_dropdown.value:
            expense_data["project_id"] = int(self.project_dropdown.value)
        else:
            expense_data["project_id"] = None

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

    # ---------- ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ ----------
    def _confirm_delete(self, expense_id):
        def close_dialog(e):
            dlg.open = False
            self.page.update()

        def confirm(e):
            self._delete_expense(expense_id)
            close_dialog(e)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirm deletion"),
            content=ft.Text("Are you sure you want to delete this operation?"),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.ElevatedButton("Delete", on_click=confirm, color=ft.Colors.RED_400),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def _delete_expense(self, expense_id):
        self.expenses = [exp for exp in self.expenses if exp["id"] != expense_id]
        save_expenses(self.expenses)
        self.update_content(self.get_view())

    def delete_expense(self, e: ft.ControlEvent):
        expense_id = e.control.data
        self._confirm_delete(expense_id)
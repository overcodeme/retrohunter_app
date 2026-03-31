import flet as ft
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

DATA_DIR = Path("data")
EXPENSES_FILE = DATA_DIR / "expenses.json"

CATEGORIES = ["Proxy", "Captcha", "Gas", "Software", "Other"]

TYPE_EXPENSE = "expense"
TYPE_INCOME = "income"

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
        for exp in data:
            if "account_id" in exp and exp["account_id"] is not None:
                exp["account_ids"] = [exp["account_id"]]
                del exp["account_id"]
            elif "account_ids" not in exp:
                exp["account_ids"] = []
            if "network" not in exp:
                exp["network"] = "evm"
            if "type" not in exp:
                exp["type"] = TYPE_EXPENSE
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
        self.date_from_field = None
        self.date_to_field = None
        self.quick_filter_dropdown = None
        self.show_charts = False

        # Поля диалога
        self.type_radio = None
        self.network_radio = None
        self.date_field = None
        self.project_dropdown = None
        self.search_field = None
        self.accounts_list = None
        self.category_dropdown = None
        self.amount_field = None
        self.desc_field = None
        self.dialog_modal = None
        self.editing_expense_id = None
        self.current_expense_accounts = []
        self.current_network = "evm"

    # ----- Вспомогательные методы для кастомной таблицы -----
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

    @staticmethod
    def amount_cell(amount: float, type_: str, width: int) -> ft.Container:
        color = ft.Colors.RED_400 if type_ == TYPE_EXPENSE else ft.Colors.GREEN_400
        sign = "-" if type_ == TYPE_EXPENSE else "+"
        text = f"{sign}${abs(amount):.2f}"
        return ft.Container(
            content=ft.Text(
                text,
                size=15,
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

    def _bytesio_to_data_url(self, buf: io.BytesIO, mime: str = "image/png") -> str:
        raw = buf.getvalue()
        b64 = base64.b64encode(raw).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def _build_charts(self, filtered: List[Dict[str, Any]]) -> ft.Container:
        # Данные по месяцам
        monthly_expenses = {}
        monthly_incomes = {}
        for exp in filtered:
            date_str = exp.get("date", "")
            if not date_str or len(date_str) < 7:
                continue
            year_month = date_str[:7]
            amount = exp.get("amount", 0)
            if exp.get("type") == TYPE_EXPENSE:
                monthly_expenses[year_month] = monthly_expenses.get(year_month, 0) + amount
            else:
                monthly_incomes[year_month] = monthly_incomes.get(year_month, 0) + amount

        months = sorted(set(monthly_expenses.keys()) | set(monthly_incomes.keys()))
        expenses_vals = [monthly_expenses.get(m, 0) for m in months]
        incomes_vals = [monthly_incomes.get(m, 0) for m in months]

        # Столбцовая диаграмма
        fig1, ax1 = plt.subplots(figsize=(8, 4))
        x = range(len(months))
        width = 0.35
        ax1.bar([i - width/2 for i in x], expenses_vals, width, label='Expenses', color='red')
        ax1.bar([i + width/2 for i in x], incomes_vals, width, label='Incomes', color='green')
        ax1.set_xlabel('Month')
        ax1.set_ylabel('Amount (USD)')
        ax1.set_title('Monthly Expenses & Incomes')
        ax1.set_xticks(x)
        ax1.set_xticklabels(months, rotation=45, ha='right')
        ax1.legend()
        plt.tight_layout()
        buf1 = io.BytesIO()
        plt.savefig(buf1, format='png')
        buf1.seek(0)
        plt.close(fig1)
        img1_src = self._bytesio_to_data_url(buf1)

        # Круговая диаграмма расходов по категориям
        category_expenses = {}
        for exp in filtered:
            if exp.get("type") == TYPE_EXPENSE:
                cat = exp.get("category", "Other")
                category_expenses[cat] = category_expenses.get(cat, 0) + exp.get("amount", 0)

        if category_expenses:
            fig2, ax2 = plt.subplots(figsize=(6, 6))
            labels = list(category_expenses.keys())
            sizes = list(category_expenses.values())
            ax2.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
            ax2.axis('equal')
            ax2.set_title('Expenses by Category')
            plt.tight_layout()
            buf2 = io.BytesIO()
            plt.savefig(buf2, format='png')
            buf2.seek(0)
            plt.close(fig2)
            img2_src = self._bytesio_to_data_url(buf2)
        else:
            img2_src = None

        charts_container = ft.Container(
            content=ft.Column([
                ft.Text("Charts", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Container(content=ft.Image(src=img1_src, fit=ft.BoxFit.CONTAIN), expand=True),
                    ft.Container(content=ft.Image(src=img2_src, fit=ft.BoxFit.CONTAIN) if img2_src else ft.Text("No data"), expand=True),
                ], spacing=10, expand=True),
            ]),
            padding=10,
        )
        return charts_container

    # ----- Основное представление -----
    def get_view(self) -> ft.Container:
        # Заголовок с кнопками
        header = ft.Row([
            ft.Text("Expenses & Incomes", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.ElevatedButton(
                "Export CSV",
                icon=ft.Icons.DOWNLOAD,
                on_click=self.export_to_csv,
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.GREY_700,
                ),
            ),
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

        # Фильтры по проекту и аккаунту
        self.filter_project_dropdown = ft.Dropdown(
            label="Filter by Project",
            options=[ft.dropdown.Option("all", "All Projects")] + self._get_project_options(),
            value="all",
            width=200,
            on_select=self.apply_filters
        )

        self.filter_account_dropdown = ft.Dropdown(
            label="Filter by Account",
            options=[ft.dropdown.Option("all", "All Accounts")] + self._get_account_options(),
            value="all",
            width=200,
            on_select=self.apply_filters
        )

        # Фильтр по датам
        self.date_from_field = ft.TextField(
            label="From",
            hint_text="YYYY-MM-DD",
            width=130,
            on_change=self.apply_filters,
        )
        self.date_to_field = ft.TextField(
            label="To",
            hint_text="YYYY-MM-DD",
            width=130,
            on_change=self.apply_filters,
        )
        self.quick_filter_dropdown = ft.Dropdown(
            label="Quick filter",
            options=[
                ft.dropdown.Option("all", "All time"),
                ft.dropdown.Option("30d", "Last 30 days"),
                ft.dropdown.Option("this_year", "This year"),
            ],
            value="all",
            width=150,
            on_select=self.on_quick_filter_change,
        )

        # Кнопка переключения графика
        toggle_charts_btn = ft.IconButton(
            icon=ft.Icons.BAR_CHART if not self.show_charts else ft.Icons.TABLE_ROWS,
            tooltip="Toggle charts",
            on_click=self.toggle_charts,
        )

        filters_row = ft.Row([
            self.filter_project_dropdown,
            self.filter_account_dropdown,
            self.date_from_field,
            self.date_to_field,
            self.quick_filter_dropdown,
            toggle_charts_btn,
        ], spacing=10, wrap=True)

        # Получаем отфильтрованные операции
        filtered = self._filtered_expenses()
        total_expenses = sum(exp.get("amount", 0) for exp in filtered if exp.get("type", TYPE_EXPENSE) == TYPE_EXPENSE)
        total_incomes = sum(exp.get("amount", 0) for exp in filtered if exp.get("type", TYPE_EXPENSE) == TYPE_INCOME)

        # Карточки итогов
        expenses_card = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.TRENDING_DOWN, size=20, color=ft.Colors.RED_400),
                ft.Text(f"Expenses: ${total_expenses:.2f}", size=16, weight=ft.FontWeight.W_500, color=ft.Colors.RED_400),
            ], spacing=5),
            padding=ft.padding.only(left=15, right=15, top=10, bottom=10),
            border_radius=20,
            bgcolor=ft.Colors.GREY_900,
        )
        incomes_card = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.TRENDING_UP, size=20, color=ft.Colors.GREEN_400),
                ft.Text(f"Incomes: ${total_incomes:.2f}", size=16, weight=ft.FontWeight.W_500, color=ft.Colors.GREEN_400),
            ], spacing=5),
            padding=ft.padding.only(left=15, right=15, top=10, bottom=10),
            border_radius=20,
            bgcolor=ft.Colors.GREY_900,
        )
        balance_card = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.ACCOUNT_BALANCE, size=20, color=ft.Colors.BLUE_400),
                ft.Text(f"Profit: ${total_incomes - total_expenses:.2f}", size=16, weight=ft.FontWeight.W_500, color=ft.Colors.BLUE_400),
            ], spacing=5),
            padding=ft.padding.only(left=15, right=15, top=10, bottom=10),
            border_radius=20,
            bgcolor=ft.Colors.GREY_900,
        )
        stats_row = ft.Row([expenses_card, incomes_card, balance_card], spacing=10)

        # Таблица или графики
        if self.show_charts:
            main_content = self._build_charts(filtered)
        else:
            main_content = self._create_expenses_table(filtered)

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=20, color=ft.Colors.GREY_800),
                filters_row,
                ft.Container(height=10),
                stats_row,
                ft.Container(height=20),
                main_content,
            ]),
            padding=20,
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
                    ft.Text("No operations", size=20, color=ft.Colors.GREY_400),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=50,
                alignment=ft.Alignment.CENTER,
                height=400,
            )

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
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            border=ft.Border(
                top=ft.BorderSide(1, ft.Colors.GREY_800),
                left=ft.BorderSide(1, ft.Colors.GREY_800),
                right=ft.BorderSide(1, ft.Colors.GREY_800),
                bottom=ft.BorderSide(1, ft.Colors.GREY_800),
            ),
            bgcolor=ft.Colors.GREY_900,
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

            if exp.get("project_id"):
                project_name = self._get_project_name(exp["project_id"])
            else:
                project_name = "Global"

            account_ids = exp.get("account_ids", [])
            accounts_text = self._format_accounts(account_ids, exp.get("network", "evm"))
            accounts_tooltip = self._get_accounts_tooltip(account_ids, exp.get("network", "evm"))

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
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
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
        return ft.Container(
            content=ft.Row([table_content], scroll=ft.ScrollMode.ALWAYS),
            height=550,
            alignment=ft.Alignment.CENTER,
        )

    def _format_accounts(self, account_ids: List[int], network: str) -> str:
        if not account_ids:
            return "-"
        count = len(account_ids)
        network_label = "EVM" if network == "evm" else "Solana"
        return f"{count} {network_label}"

    def _get_accounts_tooltip(self, account_ids: List[int], network: str) -> str:
        if not account_ids:
            return ""
        network_label = "EVM" if network == "evm" else "Solana"
        ids_str = ", ".join(str(id) for id in account_ids)
        return f"{network_label}: {ids_str}"

    def _filtered_expenses(self) -> List[Dict[str, Any]]:
        project_filter = self.filter_project_dropdown.value if self.filter_project_dropdown else "all"
        account_filter = self.filter_account_dropdown.value if self.filter_account_dropdown else "all"
        date_from = self.date_from_field.value if self.date_from_field else None
        date_to = self.date_to_field.value if self.date_to_field else None

        filtered = []
        for exp in self.expenses:
            exp_project = str(exp.get("project_id")) if exp.get("project_id") else None
            exp_accounts = exp.get("account_ids", [])

            # Фильтр по проекту
            if project_filter != "all":
                if exp_project is None:
                    pass
                elif exp_project != project_filter:
                    continue

            # Фильтр по аккаунту
            if account_filter != "all":
                if not exp_accounts:
                    continue
                if int(account_filter) not in exp_accounts:
                    continue

            # Фильтр по датам
            exp_date = exp.get("date", "")
            if date_from and exp_date < date_from:
                continue
            if date_to and exp_date > date_to:
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

    def on_quick_filter_change(self, e):
        val = self.quick_filter_dropdown.value
        now = datetime.now()
        if val == "30d":
            from_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            self.date_from_field.value = from_date
            self.date_to_field.value = now.strftime("%Y-%m-%d")
        elif val == "this_year":
            from_date = datetime(now.year, 1, 1).strftime("%Y-%m-%d")
            self.date_from_field.value = from_date
            self.date_to_field.value = now.strftime("%Y-%m-%d")
        else:
            self.date_from_field.value = ""
            self.date_to_field.value = ""
        self.apply_filters(e)

    def toggle_charts(self, e):
        self.show_charts = not self.show_charts
        self.update_content(self.get_view())

    def export_to_csv(self, e):
        filtered = self._filtered_expenses()
        if not filtered:
            return
        # Используем FilePicker для сохранения
        if not hasattr(self, 'file_picker'):
            self.file_picker = ft.FilePicker()
            self.page.overlay.append(self.file_picker)
        self.file_picker.save_file(
            dialog_title="Save CSV",
            allowed_extensions=["csv"],
            on_result=self._on_export_file_selected,
        )

    def _on_export_file_selected(self, e):
        if not e.path:
            return
        path = Path(e.path)
        if path.suffix.lower() != '.csv':
            path = path.with_suffix('.csv')
        self._do_export(path)

    def _do_export(self, path: Path):
        try:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                headers = ["Date", "Type", "Project", "Accounts", "Category", "Amount", "Description"]
                writer.writerow(headers)
                for exp in self._filtered_expenses():
                    project_name = self._get_project_name(exp.get("project_id"))
                    accounts_str = self._format_accounts(exp.get("account_ids", []), exp.get("network", "evm"))
                    writer.writerow([
                        exp.get("date", ""),
                        "Expense" if exp.get("type") == TYPE_EXPENSE else "Income",
                        project_name,
                        accounts_str,
                        exp.get("category", ""),
                        f"{exp.get('amount', 0):.2f}",
                        exp.get("description", "")
                    ])
            self.page.snack_bar = ft.SnackBar(content=ft.Text(f"Exported to {path}"), open=True)
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(f"Export failed: {ex}"), open=True)
        self.page.update()

    # ---------- ДИАЛОГ ДОБАВЛЕНИЯ/РЕДАКТИРОВАНИЯ ----------
    def open_add_expense_dialog(self, e: ft.ControlEvent = None):
        self.editing_expense_id = None
        self.current_expense_accounts = []
        self.current_network = "evm"
        self._show_expense_dialog()

    def open_edit_expense_dialog(self, e: ft.ControlEvent):
        expense_id = e.control.data
        self.editing_expense_id = expense_id
        expense = next((exp for exp in self.expenses if exp["id"] == expense_id), None)
        if expense:
            self.current_expense_accounts = expense.get("account_ids", [])
            self.current_network = expense.get("network", "evm")
            self._show_expense_dialog(expense)

    def _show_expense_dialog(self, expense: Optional[Dict] = None):
        self.type_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value=TYPE_EXPENSE, label="Expense", fill_color=ft.Colors.RED_400),
                ft.Radio(value=TYPE_INCOME, label="Income", fill_color=ft.Colors.GREEN_400),
            ]),
            value=expense.get("type") if expense else TYPE_EXPENSE,
        )
        self.network_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="evm", label="EVM", fill_color=ft.Colors.BLUE_400),
                ft.Radio(value="solana", label="Solana", fill_color=ft.Colors.PURPLE_400),
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
        self.project_dropdown = ft.Dropdown(
            label="Project (leave empty for global)",
            options=[ft.dropdown.Option("", "-- Global --")] + self._get_project_options(),
            value=str(expense.get("project_id")) if expense and expense.get("project_id") else "",
            on_select=self.on_project_change
        )

        self.search_field = ft.TextField(
            label="Search accounts",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self.filter_accounts,
            hint_text="Type to filter by private key or email",
        )
        select_all_btn = ft.TextButton("Select All", on_click=self.select_all_accounts)
        clear_all_btn = ft.TextButton("Clear All", on_click=self.clear_all_accounts)

        self.accounts_list = ft.Column(scroll=ft.ScrollMode.AUTO, height=200)
        self._build_accounts_list()

        self.dialog_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Operation" if expense else "Add New Operation"),
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
                ], scroll=ft.ScrollMode.AUTO, height=650),
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
            if network == "evm":
                key = acc.get("evm_private_key", "")
                addr = acc.get("evm_address")
            else:
                key = acc.get("sol_private_key", "")
                addr = acc.get("solana_address")
            if not key:
                continue

            searchable_string = (
                f"id:{acc['id']} "
                f"key:{key} "
                f"addr:{addr or ''} "
                f"email:{acc.get('email', '')}"
            ).lower()
            if filter_text and filter_text not in searchable_string:
                continue

            network_label = "EVM" if network == "evm" else "Solana"
            display = self._get_account_display(acc, network)
            label = f"{network_label} {acc['id']} ({display})"
            cb = ft.Checkbox(
                label=label,
                value=acc["id"] in self.current_expense_accounts,
                data=acc["id"],
            )
            checkboxes.append(cb)

        self.accounts_list.controls = checkboxes if checkboxes else [ft.Text("No matching accounts", color=ft.Colors.GREY_400)]
        self.page.update()

    def _get_account_display(self, acc: Dict, network: str) -> str:
        if network == "evm":
            address = acc.get("evm_address")
            if address:
                return address[:4] + "..." + address[-4:]
            key = acc.get("evm_private_key", "")
            if key:
                return key[:4] + "..." + key[-4:]
            return "No EVM"
        else:
            address = acc.get("solana_address")
            if address:
                return address[:4] + "..." + address[-4:]
            key = acc.get("sol_private_key", "")
            if key:
                return key[:4] + "..." + key[-4:]
            return "No Solana"

    def on_network_change(self, e):
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
        # Можно оставить пустым или добавить логику
        pass

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

        op_type = self.type_radio.value
        network = self.network_radio.value

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

    # ---------- УДАЛЕНИЕ ----------
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
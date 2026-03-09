import flet as ft
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from accounts import AccountsManager


DATA_DIR = Path("data")
PROJECTS_FILE = DATA_DIR / "projects.json"

def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)

def load_projects() -> List[Dict[str, Any]]:
    ensure_data_dir()
    if not PROJECTS_FILE.exists():
        with open(PROJECTS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []
    with open(PROJECTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_projects(projects: List[Dict[str, Any]]):
    ensure_data_dir()
    with open(PROJECTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(projects, f, indent=4, ensure_ascii=False)


class ProjectsManager:
    def __init__(self, page: ft.Page, update_content_callback, accounts_manager: AccountsManager):
        self.page = page
        self.update_content = update_content_callback
        self.accounts_manager = accounts_manager
        self.projects = load_projects()

        # Поля для диалога добавления/редактирования проекта
        self.name_field = None
        self.desc_field = None
        self.status_dropdown = None
        self.type_dropdown = None
        self.expenses_field = None
        self.add_expense_field = None
        self.start_field = None
        self.end_field = None
        self.search_field = None
        self.accounts_list = None
        self.dialog_modal = None
        self.editing_project_id = None
        self.current_project_accounts = []

    # ----- Вспомогательные методы для кастомной таблицы -----
    @staticmethod
    def centered_header(text: str, width: int) -> ft.Container:
        """Ячейка заголовка с центрированием (без переноса)"""
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
    def centered_cell(text: str, width: int, tooltip: str = "", multiline: bool = False, size = 15) -> ft.Container:
        """
        Ячейка данных с центрированием.
        Если multiline=True, текст может переноситься на несколько строк.
        """
        if multiline:
            # Для многострочного текста не ограничиваем количество строк
            text_widget = ft.Text(
                text,
                size=size,
                selectable=True,
                text_align=ft.TextAlign.CENTER,
                no_wrap=False,  # разрешаем перенос
            )
        else:
            # Для остальных – одна строка с обрезанием
            text_widget = ft.Text(
                text,
                size=size,
                selectable=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                text_align=ft.TextAlign.CENTER,
            )

        return ft.Container(
            content=text_widget,
            width=width,
            alignment=ft.Alignment.CENTER,
            padding=ft.padding.only(left=8, right=8, top=4, bottom=4),
            tooltip=tooltip if not multiline else None,  # подсказка не нужна, если текст виден полностью
        )

    @staticmethod
    def centered_status_cell(status: str, width: int) -> ft.Container:
        """Ячейка статуса с цветным кружком и текстом (центрирована, одна строка)"""
        status_colors = {
            "active": ft.Colors.GREEN_400,
            "waiting": ft.Colors.ORANGE_400,
            "completed": ft.Colors.BLUE_400,
            "cancelled": ft.Colors.GREY_400,
        }
        color = status_colors.get(status, ft.Colors.GREY_400)
        content = ft.Row([
            ft.Container(width=12, height=12, bgcolor=color, border_radius=6),
            ft.Text(status.capitalize(), size=15, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=8, alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return ft.Container(
            content=content,
            width=width,
            alignment=ft.Alignment.CENTER,
            padding=ft.padding.only(left=8, right=8, top=4, bottom=4),
        )

    # ----- Основное представление -----
    def get_view(self) -> ft.Container:
        header = ft.Row([
            ft.Text("Projects list", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.ElevatedButton(
                "Add project",
                icon=ft.Icons.ADD,
                on_click=self.open_add_project_dialog,
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=ft.Colors.BLUE_600
                )
            ),
        ])

        stats_row = ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.FOLDER_OUTLINED, size=20, color=ft.Colors.GREEN_400),
                    ft.Text(f"Total projects: {len(self.projects)}", size=16, weight=ft.FontWeight.W_500),
                ], spacing=10),
                padding=ft.padding.only(left=15, right=15, top=10, bottom=10),
                border_radius=20,
                bgcolor=ft.Colors.GREY_900
            )
        ], alignment=ft.MainAxisAlignment.START)

        col_widths = {
            "id": 50,
            "name": 150,
            "description": 350,  
            "type": 120,
            "status": 120,
            "start": 110,
            "end": 110,
            "accounts": 110,
            "expenses": 120,
            "actions": 100,
        }

        # Заголовок таблицы
        header_row = ft.Container(
            content=ft.Row([
                self.centered_header("ID", col_widths["id"]),
                self.centered_header("Name", col_widths["name"]),
                self.centered_header("Type", col_widths["type"]),
                self.centered_header("Status", col_widths["status"]),
                self.centered_header("Start", col_widths["start"]),
                self.centered_header("End", col_widths["end"]),
                self.centered_header("Accounts", col_widths["accounts"]),
                self.centered_header("Expenses", col_widths["expenses"]),
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

        if self.projects:
            # Строки данных
            rows_content = []
            for proj in self.projects:
                edit_btn = ft.IconButton(
                    icon=ft.Icons.EDIT_OUTLINED,
                    icon_color=ft.Colors.BLUE_400,
                    tooltip="Edit project",
                    data=proj.get("id"),
                    on_click=self.open_edit_project_dialog,
                    width=32,
                    height=32,
                    padding=0,
                    icon_size=20,
                )
                delete_btn = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=ft.Colors.RED_400,
                    tooltip="Delete project",
                    data=proj.get("id"),
                    on_click=self.delete_project,
                    width=32,
                    height=32,
                    padding=0,
                    icon_size=20,
                )

                name = proj.get("name", "")
                description = proj.get("description", "")  # может быть многострочным
                project_type = proj.get("type", "other").capitalize()
                status = proj.get("status", "unknown")
                start = proj.get("start_date", "")
                end = proj.get("end_date", "")
                accounts_count = str(len(proj.get("accounts", [])))
                expenses = proj.get("expenses", 0)
                expenses_str = f"${expenses:.2f}" if expenses else "-"

                row = ft.Container(
                    content=ft.Row([
                        self.centered_cell(str(proj.get("id", "")), col_widths["id"]),
                        self.centered_cell(name, col_widths["name"], tooltip=name),
                        self.centered_cell(project_type, col_widths["type"]),
                        self.centered_status_cell(status, col_widths["status"]),
                        self.centered_cell(start, col_widths["start"]),
                        self.centered_cell(end, col_widths["end"]),
                        self.centered_cell(accounts_count, col_widths["accounts"]),
                        self.centered_cell(expenses_str, col_widths["expenses"]),
                        self.centered_cell(description, col_widths["description"], multiline=True, size=10),
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
                    ft.Icon(ft.Icons.FOLDER_OUTLINED, size=64, color=ft.Colors.GREY_600),
                    ft.Text("No projects yet", size=20, color=ft.Colors.GREY_400),
                    ft.Text("Click 'Add project' to add a project", color=ft.Colors.GREY_500),
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

    def open_add_project_dialog(self, e: ft.ControlEvent = None):
        self.editing_project_id = None
        self.current_project_accounts = []
        self._show_project_dialog()

    def open_edit_project_dialog(self, e: ft.ControlEvent):
        project_id = e.control.data
        self.editing_project_id = project_id
        project = next((p for p in self.projects if p["id"] == project_id), None)
        if project:
            self.current_project_accounts = project.get("accounts", [])
            self._show_project_dialog(project)

    def _show_project_dialog(self, project: Optional[Dict] = None):
        self.name_field = ft.TextField(
            label="Project Name *",
            value=project.get("name") if project else "",
        )
        self.desc_field = ft.TextField(
            label="Description",
            value=project.get("description") if project else "",
            multiline=True,
            min_lines=2,
            max_lines=4,
        )
        self.status_dropdown = ft.Dropdown(
            label="Status",
            options=[
                ft.dropdown.Option("active", "Active"),
                ft.dropdown.Option("waiting", "Waiting"),
                ft.dropdown.Option("completed", "Completed"),
                ft.dropdown.Option("cancelled", "Cancelled"),
            ],
            value=project.get("status") if project else "waiting",
        )
        self.type_dropdown = ft.Dropdown(
            label="Project Type",
            options=[
                ft.dropdown.Option("testnet", "Testnet"),
                ft.dropdown.Option("mainnet", "Mainnet"),
                ft.dropdown.Option("dex", "DEX"),
                ft.dropdown.Option("social", "Social"),
                ft.dropdown.Option("gamefi", "GameFi"),
                ft.dropdown.Option("other", "Other"),
            ],
            value=project.get("type") if project else "testnet",
        )
        self.start_field = ft.TextField(
            label="Start Date (YYYY-MM-DD)",
            value=project.get("start_date") if project else "",
            hint_text="2025-01-01",
        )
        self.end_field = ft.TextField(
            label="End Date (YYYY-MM-DD)",
            value=project.get("end_date") if project else "",
            hint_text="2025-12-31",
        )

        self.expenses_field = ft.TextField(
            label="Total expenses (USD)",
            value=str(project.get("expenses", "0.0")) if project else "0.0",
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="0.00",
            width=200,
        )

        self.add_expense_field = ft.TextField(
            label="Add expense",
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="0.00",
            width=150,
        )
        add_btn = ft.IconButton(
            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
            icon_color=ft.Colors.GREEN_400,
            tooltip="Add to total",
            on_click=self.add_expense_to_total,
        )
        expenses_row = ft.Row([self.expenses_field, self.add_expense_field, add_btn], alignment=ft.MainAxisAlignment.START)

        self.search_field = ft.TextField(
            label="Search accounts",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self.filter_accounts,
            hint_text="Type to filter by private key or email",
        )

        select_all_btn = ft.TextButton("Select All", on_click=self.select_all_accounts)
        clear_all_btn = ft.TextButton("Clear All", on_click=self.clear_all_accounts)

        self.accounts_list = ft.Column(scroll=ft.ScrollMode.AUTO, height=300)
        self._build_accounts_list()

        self.dialog_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Project" if project else "Add New Project"),
            content=ft.Container(
                content=ft.Column([
                    self.name_field,
                    self.desc_field,
                    ft.Row([self.status_dropdown, self.type_dropdown], spacing=10),
                    ft.Row([self.start_field, self.end_field], spacing=10),
                    expenses_row,
                    ft.Divider(height=10, color=ft.Colors.GREY_800),
                    ft.Text("Select accounts for this project:", size=14, weight=ft.FontWeight.BOLD),
                    ft.Row([select_all_btn, clear_all_btn], alignment=ft.MainAxisAlignment.START),
                    self.search_field,
                    ft.Container(
                        content=self.accounts_list,
                        border=ft.Border.all(1, ft.Colors.GREY_800),
                        border_radius=5,
                        padding=10,
                        height=300,
                    ),
                ], scroll=ft.ScrollMode.AUTO, height=650),
                width=750,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog),
                ft.ElevatedButton("Save", on_click=self.save_project),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(self.dialog_modal)
        self.page.update()

    def _build_accounts_list(self, filter_text: str = ""):
        """Заполняет accounts_list чекбоксами на основе фильтра"""
        if not self.accounts_manager or not self.accounts_manager.accounts:
            self.accounts_list.controls = [ft.Text("No accounts available", color=ft.Colors.GREY_400)]
            return

        checkboxes = []
        filter_text = filter_text.lower()
        for acc in self.accounts_manager.accounts:
            searchable_string = (
                f"id:{acc['id']} "
                f"evm:{acc.get('evm_private_key', '')} "
                f"sol:{acc.get('sol_private_key', '')} "
                f"email:{acc.get('email', '')}"
            ).lower()

            if filter_text and filter_text not in searchable_string:
                continue

            evm_short = acc.get('evm_private_key', '')[:8] + "..." + acc.get("evm_private_key")[-4:] if acc.get('evm_private_key') else "No key"
            label = f"ID {acc['id']} ({evm_short})"
            cb = ft.Checkbox(
                label=label,
                value=acc["id"] in self.current_project_accounts,
                data=acc["id"],
            )
            checkboxes.append(cb)

        self.accounts_list.controls = checkboxes if checkboxes else [ft.Text("No matching accounts", color=ft.Colors.GREY_400)]
        self.page.update()

    def add_expense_to_total(self, e):
        try:
            current = float(self.expenses_field.value or "0")
            add_amount = float(self.add_expense_field.value or "0")
            if add_amount > 0:
                self.expenses_field.value = f"{current + add_amount:.2f}"
                self.add_expense_field.value = ""
                self.page.update()
        except ValueError:
            pass

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

    def close_dialog(self, e: ft.ControlEvent = None):
        self.dialog_modal.open = False
        self.page.update()

    def save_project(self, e: ft.ControlEvent = None):
        name = self.name_field.value.strip()
        if not name:
            return

        selected_accounts = [
            cb.data for cb in self.accounts_list.controls
            if isinstance(cb, ft.Checkbox) and cb.value
        ]

        try:
            expenses = float(self.expenses_field.value or "0")
        except ValueError:
            expenses = 0.0

        if self.editing_project_id is None:
            new_id = max([p["id"] for p in self.projects], default=0) + 1
            new_project = {
                "id": new_id,
                "name": name,
                "description": self.desc_field.value,
                "status": self.status_dropdown.value,
                "type": self.type_dropdown.value,
                "start_date": self.start_field.value,
                "end_date": self.end_field.value,
                "expenses": expenses,
                "accounts": selected_accounts,
            }
            self.projects.append(new_project)
        else:
            for proj in self.projects:
                if proj["id"] == self.editing_project_id:
                    proj.update({
                        "name": name,
                        "description": self.desc_field.value,
                        "status": self.status_dropdown.value,
                        "type": self.type_dropdown.value,
                        "start_date": self.start_field.value,
                        "end_date": self.end_field.value,
                        "expenses": expenses,
                        "accounts": selected_accounts,
                    })
                    break

        save_projects(self.projects)
        self.close_dialog()
        self.update_content(self.get_view())

    def delete_project(self, e: ft.ControlEvent):
        project_id = e.control.data
        self.projects = [p for p in self.projects if p["id"] != project_id]
        save_projects(self.projects)
        self.update_content(self.get_view())
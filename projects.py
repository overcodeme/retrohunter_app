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
        self.expenses_manager = None  # будет установлен позже
        self.projects = load_projects()

        # Поля для диалога добавления/редактирования проекта
        self.name_field = None
        self.desc_field = None
        self.status_dropdown = None
        self.type_dropdown = None
        self.start_field = None
        self.end_field = None
        self.search_field = None
        self.accounts_list = None
        self.dialog_modal = None
        self.editing_project_id = None
        self.current_project_accounts = []

    def set_expenses_manager(self, expenses_manager):
        """Устанавливает ссылку на менеджер расходов для расчёта суммы по проекту"""
        self.expenses_manager = expenses_manager

    # ----- Вспомогательные методы для кастомной таблицы -----
    @staticmethod
    def centered_header(text: str, width: int) -> ft.Container:
        """Ячейка заголовка с центрированием (шрифт 16)"""
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
    def centered_cell(text: str, width: int, tooltip: str = "") -> ft.Container:
        """Ячейка данных с центрированием (одна строка + подсказка)"""
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
    def centered_status_cell(status: str, width: int) -> ft.Container:
        """Ячейка статуса с цветным кружком и текстом (центрирована)"""
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

    def _format_tooltip(self, text: str, max_chars: int = 50) -> str:
        """Разбивает длинный текст на строки по max_chars символов для компактной подсказки"""
        if not text:
            return text
        words = text.split(' ')
        lines = []
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= max_chars:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return '\n'.join(lines)

    def _get_project_expenses(self, project_id: int) -> float:
        """Возвращает сумму всех расходов, связанных с данным проектом (из expenses_manager)"""
        if not self.expenses_manager:
            return 0.0
        total = 0.0
        for exp in self.expenses_manager.expenses:
            if exp.get("project_id") == project_id:
                total += exp.get("amount", 0)
        return total

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

        # Ширины колонок
        col_widths = {
            "id": 50,
            "name": 250,
            "type": 120,
            "status": 120,
            "start": 110,
            "end": 110,
            "acc": 70,
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
                self.centered_header("Acc", col_widths["acc"]),
                self.centered_header("Expenses", col_widths["expenses"]),
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
                description = proj.get("description", "")
                formatted_desc = self._format_tooltip(description, 50)
                name_cell = self.centered_cell(name, col_widths["name"], tooltip=formatted_desc)

                project_type = proj.get("type", "other").capitalize()
                status = proj.get("status", "unknown")
                start = proj.get("start_date", "")
                end = proj.get("end_date", "")
                accounts_count = str(len(proj.get("accounts", [])))
                expenses = self._get_project_expenses(proj["id"])
                expenses_str = f"${expenses:.2f}" if expenses else "-"

                row = ft.Container(
                    content=ft.Row([
                        self.centered_cell(str(proj.get("id", "")), col_widths["id"]),
                        name_cell,
                        self.centered_cell(project_type, col_widths["type"]),
                        self.centered_status_cell(status, col_widths["status"]),
                        self.centered_cell(start, col_widths["start"]),
                        self.centered_cell(end, col_widths["end"]),
                        self.centered_cell(accounts_count, col_widths["acc"]),
                        self.centered_cell(expenses_str, col_widths["expenses"]),
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
            padding=20
        )

    # ---------- ДИАЛОГИ ----------
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

        # Поиск аккаунтов
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
                ], scroll=ft.ScrollMode.AUTO, height=600),
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

            evm_short = acc.get('evm_private_key', '')[:8] + "..." if acc.get('evm_private_key') else "No key"
            label = f"ID {acc['id']} ({evm_short})"
            cb = ft.Checkbox(
                label=label,
                value=acc["id"] in self.current_project_accounts,
                data=acc["id"],
            )
            checkboxes.append(cb)

        self.accounts_list.controls = checkboxes if checkboxes else [ft.Text("No matching accounts", color=ft.Colors.GREY_400)]
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
                        "accounts": selected_accounts,
                    })
                    break

        save_projects(self.projects)
        self.close_dialog()
        self.update_content(self.get_view())

    # ---------- ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ ----------
    def _confirm_delete(self, project_id):
        def close_dialog(e):
            dlg.open = False
            self.page.update()

        def confirm(e):
            self._delete_project(project_id)
            close_dialog(e)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirm deletion"),
            content=ft.Text("Are you sure you want to delete this project?"),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.ElevatedButton("Delete", on_click=confirm, color=ft.Colors.RED_400),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def _delete_project(self, project_id):
        self.projects = [p for p in self.projects if p["id"] != project_id]
        save_projects(self.projects)
        self.update_content(self.get_view())

    def delete_project(self, e: ft.ControlEvent):
        project_id = e.control.data
        self._confirm_delete(project_id)
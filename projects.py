import flet as ft
import json
import datetime
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
        self.expenses_manager = None
        self.projects = load_projects()

        # Поля для диалога
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

        self.filter_search = ft.TextField(
            label="Search projects",
            prefix_icon=ft.Icons.SEARCH,
            hint_text="Name, description, type...",
            on_submit=self.apply_filters,
            expand=True,
        )
        
        self.filter_type = ft.Dropdown(
            label="Type",
            options=[ft.dropdown.Option("all", "All types")] + [
                ft.dropdown.Option("testnet", "Testnet"),
                ft.dropdown.Option("mainnet", "Mainnet"),
                ft.dropdown.Option("dex", "DEX"),
                ft.dropdown.Option("social", "Social"),
                ft.dropdown.Option("gamefi", "GameFi"),
                ft.dropdown.Option("other", "Other"),
            ],
            value="all",
            width=150,
            on_select=self.apply_filters,
        )

        self.filter_status = ft.Dropdown(
            label="Status",
            options=[ft.dropdown.Option("all", "All statuses")] + [
                ft.dropdown.Option("active", "Active"),
                ft.dropdown.Option("waiting", "Waiting"),
                ft.dropdown.Option("completed", "Completed"),
                ft.dropdown.Option("cancelled", "Cancelled"),
            ],
            value="all",
            width=150,
            on_select=self.apply_filters,
        )

        self.filter_expense = ft.Dropdown(
            label="Expenses",
            options=[
                ft.dropdown.Option("all", "All"),
                ft.dropdown.Option("with", "With expenses"),
                ft.dropdown.Option("without", "Without expenses"),
            ],
            value="all",
            width=150,
            on_select=self.apply_filters,
        )

    def set_expenses_manager(self, expenses_manager):
        self.expenses_manager = expenses_manager

    # ----- Вспомогательные методы -----
    def _format_tooltip(self, text: str, max_chars: int = 50) -> str:
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
        if not self.expenses_manager:
            return 0.0
        total = 0.0
        for exp in self.expenses_manager.expenses:
            if exp.get("project_id") == project_id:
                total += exp.get("amount", 0)
        return total

    def _get_status_color(self, status: str) -> ft.Colors:
        colors = {
            "active": ft.Colors.GREEN_400,
            "waiting": ft.Colors.ORANGE_400,
            "completed": ft.Colors.BLUE_400,
            "cancelled": ft.Colors.GREY_400,
        }
        return colors.get(status, ft.Colors.GREY_400)

    def _matches_filters(self, project: Dict) -> bool:
        """Проверяет, соответствует ли проект текущим фильтрам"""
        # Поиск по тексту
        if self.filter_search.value:
            search_text = self.filter_search.value.lower()
            name = project.get("name", "").lower()
            desc = project.get("description", "").lower()
            type_ = project.get("type", "").lower()
            if not (search_text in name or search_text in desc or search_text in type_):
                return False

        # Фильтр по типу
        if self.filter_type.value != "all" and project.get("type") != self.filter_type.value:
            return False

        # Фильтр по статусу
        if self.filter_status.value != "all" and project.get("status") != self.filter_status.value:
            return False

        # Фильтр по расходам
        if self.filter_expense.value != "all":
            expenses = self._get_project_expenses(project["id"])
            if self.filter_expense.value == "with" and expenses <= 0:
                return False
            if self.filter_expense.value == "without" and expenses > 0:
                return False

        return True

    # ----- Создание карточки проекта -----
    def _build_project_card(self, project: Dict) -> ft.Container:
        project_id = project["id"]
        name = project.get("name", "")
        description = project.get("description", "")
        project_type = project.get("type", "other").capitalize()
        status = project.get("status", "unknown")
        start = project.get("start_date", "")
        end = project.get("end_date", "")
        accounts_count = len(project.get("accounts", []))
        expenses = self._get_project_expenses(project_id)
        expenses_str = f"${expenses:.2f}" if expenses else "-"

        status_color = self._get_status_color(status)

        edit_btn = ft.IconButton(
            icon=ft.Icons.EDIT_OUTLINED,
            icon_color=ft.Colors.BLUE_400,
            tooltip="Edit project",
            data=project_id,
            on_click=self.open_edit_project_dialog,
            width=36,
            height=36,
            padding=0,
            icon_size=22,
        )
        delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.RED_400,
            tooltip="Delete project",
            data=project_id,
            on_click=self.delete_project,
            width=36,
            height=36,
            padding=0,
            icon_size=22,
        )

        # Прогресс-бар на основе дат
        progress_value = None
        if start and end:
            try:
                start_date = datetime.datetime.strptime(start, "%Y-%m-%d")
                end_date = datetime.datetime.strptime(end, "%Y-%m-%d")
                today = datetime.datetime.now()
                if today < start_date:
                    progress_value = 0.0
                elif today > end_date:
                    progress_value = 1.0
                else:
                    total_days = (end_date - start_date).days
                    passed_days = (today - start_date).days
                    if total_days > 0:
                        progress_value = passed_days / total_days
            except:
                progress_value = None

        card_content = ft.Column([
            ft.Row([
                ft.Container(
                    width=12, height=12, bgcolor=status_color, border_radius=6,
                ),
                ft.Text(name, size=18, weight=ft.FontWeight.BOLD, expand=True),
                edit_btn,
                delete_btn,
            ], alignment=ft.MainAxisAlignment.START),
            ft.Text(
                self._format_tooltip(description, 60),
                size=13,
                color=ft.Colors.GREY_400,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
                tooltip=description,
            ) if description else ft.Container(),
            ft.Divider(height=10, color=ft.Colors.GREY_800),
            ft.Row([
                ft.Icon(ft.Icons.LABEL_OUTLINE, size=14, color=ft.Colors.GREY_400),
                ft.Text(project_type, size=14),
            ], spacing=5),
            ft.Row([
                ft.Icon(ft.Icons.CALENDAR_TODAY, size=14, color=ft.Colors.GREY_400),
                ft.Text(f"{start} - {end}", size=14),
            ], spacing=5),
            ft.Row([
                ft.Icon(ft.Icons.PEOPLE_OUTLINE, size=14, color=ft.Colors.GREY_400),
                ft.Text(f"{accounts_count} accounts", size=14),
                ft.Container(expand=True),
                ft.Text(expenses_str, size=14, color=ft.Colors.GREEN_400, weight=ft.FontWeight.BOLD),
            ], spacing=5),
            ft.Container(height=5),
            ft.ProgressBar(value=progress_value, color=status_color, bgcolor=ft.Colors.GREY_800, height=6, border_radius=3) if progress_value is not None else ft.Container(),
        ])

        return ft.Container(
            content=card_content,
            width=320,
            padding=15,
            border_radius=12,
            bgcolor=ft.Colors.GREY_900,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK)),
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

        # Строка поиска с кнопкой
        search_button = ft.IconButton(
            icon=ft.Icons.SEARCH,
            tooltip="Search",
            on_click=self.apply_filters,
        )
        search_row = ft.Row([
            self.filter_search,
            search_button,
        ])

        # Строка фильтров (без кнопки Apply, так как on_select срабатывает автоматически)
        filters_row = ft.Row([
            self.filter_type,
            self.filter_status,
            self.filter_expense,
        ], spacing=10, wrap=True)

        # Статистика (количество отфильтрованных проектов)
        filtered_projects = [p for p in self.projects if self._matches_filters(p)]
        stats_row = ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.FOLDER_OUTLINED, size=20, color=ft.Colors.GREEN_400),
                    ft.Text(f"Projects: {len(filtered_projects)} / {len(self.projects)}", size=16, weight=ft.FontWeight.W_500),
                ], spacing=10),
                padding=ft.padding.only(left=15, right=15, top=10, bottom=10),
                border_radius=20,
                bgcolor=ft.Colors.GREY_900
            )
        ], alignment=ft.MainAxisAlignment.START)

        if filtered_projects:
            cards = [self._build_project_card(p) for p in filtered_projects]
            projects_grid = ft.GridView(
                controls=cards,
                expand=True,
                runs_count=3,
                max_extent=350,
                spacing=10,
                run_spacing=10,
                padding=10,
            )
            grid_container = ft.Container(
                content=projects_grid,
                height=500,
            )
        else:
            grid_container = ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.FOLDER_OUTLINED, size=64, color=ft.Colors.GREY_600),
                    ft.Text("No projects match your filters", size=20, color=ft.Colors.GREY_400),
                    ft.Text("Try adjusting search or filters", color=ft.Colors.GREY_500),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=50,
                alignment=ft.Alignment.CENTER,
                height=400,
            )

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=20, color=ft.Colors.GREY_800),
                search_row,
                ft.Container(height=10),
                filters_row,
                ft.Container(height=10),
                stats_row,
                ft.Container(height=20),
                grid_container,
            ]),
            padding=20
        )

    def apply_filters(self, e):
        """Обновляет представление при изменении фильтров"""
        self.update_content(self.get_view())

    # ---------- Диалоги и функциональность ----------
    def open_add_project_dialog(self, e: ft.ControlEvent = None):
        self.editing_project_id = None
        self.current_project_accounts = []
        self._show_project_dialog()

    def open_edit_project_dialog(self, e: ft.ControlEvent):
        project_id = e.control.data
        if not project_id:
            return
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

    # ---------- Подтверждение удаления ----------
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
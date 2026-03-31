import flet as ft
import json
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from accounts import AccountsManager

DATA_DIR = Path("data")
PROJECTS_FILE = DATA_DIR / "projects.json"
IMAGES_DIR = DATA_DIR / "images"

NETWORK_EVM = "evm"
NETWORK_SOLANA = "solana"

def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)

def load_projects() -> List[Dict[str, Any]]:
    ensure_data_dir()
    if not PROJECTS_FILE.exists():
        with open(PROJECTS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []
    with open(PROJECTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for proj in data:
            if "network" not in proj:
                proj["network"] = NETWORK_EVM
            if "image_path" not in proj:
                proj["image_path"] = None
            if "archived" not in proj:
                proj["archived"] = False
        return data

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

        # Поля для выбора сети и изображения
        self.network_radio = None
        self.current_network = NETWORK_EVM
        self.image_preview = None
        self.selected_image_path = None
        self.file_picker = None

        # Фильтры и сортировка
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

        # Фильтр по дате начала
        self.start_date_from = ft.TextField(
            label="Start date from",
            hint_text="YYYY-MM-DD",
            width=130,
            on_change=self.apply_filters,
        )
        self.start_date_to = ft.TextField(
            label="to",
            hint_text="YYYY-MM-DD",
            width=130,
            on_change=self.apply_filters,
        )

        # Чекбокс для архива
        self.show_archived = ft.Checkbox(
            label="Show archived",
            value=False,
            on_change=self.apply_filters,
        )

        # Сортировка
        self.sort_by = ft.Dropdown(
            label="Sort by",
            options=[
                ft.dropdown.Option("name", "Name"),
                ft.dropdown.Option("start_date", "Start date"),
                ft.dropdown.Option("end_date", "End date"),
                ft.dropdown.Option("expenses", "Expenses"),
                ft.dropdown.Option("accounts_count", "Accounts count"),
            ],
            value="name",
            width=150,
            on_select=self.apply_filters,
        )
        self.sort_order = ft.Dropdown(
            label="Order",
            options=[
                ft.dropdown.Option("asc", "Ascending"),
                ft.dropdown.Option("desc", "Descending"),
            ],
            value="asc",
            width=150,
            on_select=self.apply_filters,
        )

    def set_expenses_manager(self, expenses_manager):
        self.expenses_manager = expenses_manager

    # ----- Вспомогательные методы -----
    def _format_tooltip(self, text: str, max_chars: int = 50) -> str:
        """Разбивает длинный текст на строки по max_chars символов"""
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

    def _get_project_finances(self, project_id: int):
        expenses = 0.0
        incomes = 0.0
        if self.expenses_manager:
            for exp in self.expenses_manager.expenses:
                if exp.get("project_id") == project_id:
                    amount = exp.get("amount", 0)
                    if exp.get("type") == "expense":
                        expenses += amount
                    else:
                        incomes += amount
        return expenses, incomes

    def _get_status_color(self, status: str) -> ft.Colors:
        colors = {
            "active": ft.Colors.GREEN_400,
            "waiting": ft.Colors.ORANGE_400,
            "completed": ft.Colors.BLUE_400,
            "cancelled": ft.Colors.GREY_400,
        }
        return colors.get(status, ft.Colors.GREY_400)

    def _get_account_display(self, acc: Dict, network: str) -> str:
        if network == NETWORK_EVM:
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

    def _matches_filters(self, project: Dict) -> bool:
        """Проверяет, соответствует ли проект текущим фильтрам (кроме сортировки)"""
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
            expenses, _ = self._get_project_finances(project["id"])
            if self.filter_expense.value == "with" and expenses <= 0:
                return False
            if self.filter_expense.value == "without" and expenses > 0:
                return False

        # Фильтр по дате начала
        start_date = project.get("start_date", "")
        if start_date:
            if self.start_date_from.value and start_date < self.start_date_from.value:
                return False
            if self.start_date_to.value and start_date > self.start_date_to.value:
                return False

        # Фильтр архива
        if not self.show_archived.value and project.get("archived", False):
            return False

        return True

    def _get_sorted_projects(self, projects: List[Dict]) -> List[Dict]:
        """Сортирует список проектов по выбранному полю и порядку"""
        sort_key = self.sort_by.value
        reverse = (self.sort_order.value == "desc")

        if sort_key == "name":
            return sorted(projects, key=lambda p: p.get("name", ""), reverse=reverse)
        elif sort_key == "start_date":
            return sorted(projects, key=lambda p: p.get("start_date", ""), reverse=reverse)
        elif sort_key == "end_date":
            return sorted(projects, key=lambda p: p.get("end_date", ""), reverse=reverse)
        elif sort_key == "expenses":
            return sorted(projects, key=lambda p: self._get_project_finances(p["id"])[0], reverse=reverse)
        elif sort_key == "accounts_count":
            return sorted(projects, key=lambda p: len(p.get("accounts", [])), reverse=reverse)
        else:
            return projects

    # ----- Создание карточки проекта -----
    def _build_project_card(self, project: Dict) -> ft.Container:
        project_id = project["id"]
        name = project.get("name", "")
        description = project.get("description", "")
        project_type = project.get("type", "other").capitalize()
        status = project.get("status", "unknown")
        network = project.get("network", NETWORK_EVM).capitalize()
        start = project.get("start_date", "")
        end = project.get("end_date", "")
        accounts_count = len(project.get("accounts", []))
        expenses, incomes = self._get_project_finances(project_id)
        archived = project.get("archived", False)

        status_color = self._get_status_color(status)
        image_path = project.get("image_path")
        avatar = None
        if image_path and Path(image_path).exists():
            avatar = ft.Container(
                content=ft.Image(src=image_path, fit=ft.BoxFit.COVER),  # исправлено
                width=40,
                height=40,
                border_radius=20,
                bgcolor=ft.Colors.GREY_800,
                margin=ft.margin.only(right=10),
            )
        else:
            avatar = ft.Container(
                content=ft.Icon(ft.Icons.IMAGE, size=24, color=ft.Colors.GREY_400),
                width=40,
                height=40,
                border_radius=20,
                bgcolor=ft.Colors.GREY_800,
                alignment=ft.alignment.center,
                margin=ft.margin.only(right=10),
            )

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
        archive_btn = ft.IconButton(
            icon=ft.Icons.ARCHIVE_OUTLINED if not archived else ft.Icons.UNARCHIVE,
            icon_color=ft.Colors.YELLOW_400,
            tooltip="Archive" if not archived else "Unarchive",
            data=project_id,
            on_click=self.toggle_archive,
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

        display_desc = description[:80] + "..." if len(description) > 80 else description
        tooltip_desc = self._format_tooltip(description, 50)

        finance_row = ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.TRENDING_DOWN, size=14, color=ft.Colors.RED_400),
                ft.Text(f"-${expenses:.2f}", size=14, color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD),
            ], spacing=5) if expenses > 0 else ft.Container(),
            ft.Row([
                ft.Icon(ft.Icons.TRENDING_UP, size=14, color=ft.Colors.GREEN_400),
                ft.Text(f"+${incomes:.2f}", size=14, color=ft.Colors.GREEN_400, weight=ft.FontWeight.BOLD),
            ], spacing=5) if incomes > 0 else ft.Container(),
        ], spacing=2)

        card_content = ft.Column([
            ft.Row([
                avatar,
                ft.Column([
                    ft.Row([
                        ft.Container(
                            width=12, height=12, bgcolor=status_color, border_radius=6,
                        ),
                        ft.Text(name, size=18, weight=ft.FontWeight.BOLD, expand=True),
                        edit_btn,
                        archive_btn,
                        delete_btn,
                    ], alignment=ft.MainAxisAlignment.START),
                    ft.Text(
                        display_desc,
                        size=13,
                        color=ft.Colors.GREY_400,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        tooltip=tooltip_desc,
                    ) if description else ft.Container(),
                ], expand=True),
            ], alignment=ft.MainAxisAlignment.START),
            ft.Divider(height=10, color=ft.Colors.GREY_800),
            ft.Row([
                ft.Icon(ft.Icons.LABEL_OUTLINE, size=14, color=ft.Colors.GREY_400),
                ft.Text(project_type, size=14),
            ], spacing=5),
            ft.Row([
                ft.Icon(ft.Icons.DNS_OUTLINED, size=14, color=ft.Colors.GREY_400),
                ft.Text(network, size=14),
            ], spacing=5),
            ft.Row([
                ft.Icon(ft.Icons.CALENDAR_TODAY, size=14, color=ft.Colors.GREY_400),
                ft.Text(f"{start} - {end}", size=14),
            ], spacing=5),
            ft.Row([
                ft.Icon(ft.Icons.PEOPLE_OUTLINE, size=14, color=ft.Colors.GREY_400),
                ft.Text(f"{accounts_count} accounts", size=14),
                ft.Container(expand=True),
            ], spacing=5),
            finance_row,
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

        # Фильтры: тип, статус, расходы, даты, архив
        filters_row1 = ft.Row([
            self.filter_type,
            self.filter_status,
            self.filter_expense,
        ], spacing=10, wrap=True)
        filters_row2 = ft.Row([
            ft.Text("Start date:", size=14),
            self.start_date_from,
            self.start_date_to,
            self.show_archived,
        ], spacing=10, wrap=True)
        filters_row3 = ft.Row([
            self.sort_by,
            self.sort_order,
        ], spacing=10, wrap=True)

        # Статистика (количество отфильтрованных проектов)
        filtered = [p for p in self.projects if self._matches_filters(p)]
        sorted_projects = self._get_sorted_projects(filtered)
        stats_row = ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.FOLDER_OUTLINED, size=20, color=ft.Colors.GREEN_400),
                    ft.Text(f"Projects: {len(sorted_projects)} / {len(self.projects)}", size=16, weight=ft.FontWeight.W_500),
                ], spacing=10),
                padding=ft.padding.only(left=15, right=15, top=10, bottom=10),
                border_radius=20,
                bgcolor=ft.Colors.GREY_900
            )
        ], alignment=ft.MainAxisAlignment.START)

        if sorted_projects:
            cards = [self._build_project_card(p) for p in sorted_projects]
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
                filters_row1,
                filters_row2,
                filters_row3,
                ft.Container(height=10),
                stats_row,
                ft.Container(height=20),
                grid_container,
            ]),
            padding=20
        )

    def apply_filters(self, e):
        self.update_content(self.get_view())

    # ---------- ДИАЛОГ ПРОЕКТА (с выбором сети, изображения и дат через DatePicker) ----------
    def open_add_project_dialog(self, e: ft.ControlEvent = None):
        self.editing_project_id = None
        self.current_project_accounts = []
        self.current_network = NETWORK_EVM
        self.selected_image_path = None
        self._show_project_dialog()

    def open_edit_project_dialog(self, e: ft.ControlEvent):
        project_id = e.control.data
        if not project_id:
            return
        self.editing_project_id = project_id
        project = next((p for p in self.projects if p["id"] == project_id), None)
        if project:
            self.current_project_accounts = project.get("accounts", [])
            self.current_network = project.get("network", NETWORK_EVM)
            self.selected_image_path = project.get("image_path")
            self._show_project_dialog(project)

    def _on_image_picked(self, e):
        if e.files and len(e.files) > 0:
            self.selected_image_path = e.files[0].path
            if self.image_preview:
                self.image_preview.content = ft.Image(src=self.selected_image_path, fit=ft.BoxFit.COVER)  # исправлено
                self.image_preview.update()
        self.page.update()

    def _on_start_date_picked(self, e):
        if e.control.value:
            self.start_field.value = e.control.value.strftime("%Y-%m-%d")
            self.start_field.update()

    def _on_end_date_picked(self, e):
        if e.control.value:
            self.end_field.value = e.control.value.strftime("%Y-%m-%d")
            self.end_field.update()

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

        # Поля дат с календарём
        self.start_field = ft.TextField(
            label="Start Date (YYYY-MM-DD)",
            value=project.get("start_date") if project else "",
            hint_text="2025-01-01",
            suffix=ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=self._open_start_date_picker),
        )
        self.end_field = ft.TextField(
            label="End Date (YYYY-MM-DD)",
            value=project.get("end_date") if project else "",
            hint_text="2025-12-31",
            suffix=ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=self._open_end_date_picker),
        )

        self.network_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value=NETWORK_EVM, label="EVM", fill_color=ft.Colors.BLUE_400),
                ft.Radio(value=NETWORK_SOLANA, label="Solana", fill_color=ft.Colors.PURPLE_400),
            ]),
            value=self.current_network,
            on_change=self.on_network_change,
        )

        # FilePicker для изображения
        if not self.file_picker:
            self.file_picker = ft.FilePicker(on_result=self._on_image_picked)
            self.page.overlay.append(self.file_picker)

        choose_image_btn = ft.ElevatedButton(
            "Choose image",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda _: self.file_picker.pick_files(allow_multiple=False, allowed_extensions=["png", "jpg", "jpeg", "gif"]),
        )
        self.image_preview = ft.Container(
            content=ft.Image(src=self.selected_image_path, fit=ft.BoxFit.COVER) if self.selected_image_path and Path(self.selected_image_path).exists() else ft.Icon(ft.Icons.IMAGE, size=48),
            width=80,
            height=80,
            border_radius=40,
            bgcolor=ft.Colors.GREY_800,
            alignment=ft.alignment.center,
        )
        clear_image_btn = ft.IconButton(
            icon=ft.Icons.CLEAR,
            tooltip="Remove image",
            on_click=lambda _: self._clear_image(),
        )

        self.search_field = ft.TextField(
            label="Search accounts",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self.filter_accounts,
            hint_text="Type to filter by address or email",
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
                    ft.Text("Project image:", size=14, weight=ft.FontWeight.BOLD),
                    ft.Row([choose_image_btn, self.image_preview, clear_image_btn], spacing=10),
                    ft.Divider(height=10, color=ft.Colors.GREY_800),
                    ft.Text("Select accounts for this project:", size=14, weight=ft.FontWeight.BOLD),
                    self.network_radio,
                    ft.Row([select_all_btn, clear_all_btn], alignment=ft.MainAxisAlignment.START),
                    self.search_field,
                    ft.Container(
                        content=self.accounts_list,
                        border=ft.Border.all(1, ft.Colors.GREY_800),
                        border_radius=5,
                        padding=10,
                        height=300,
                    ),
                ], scroll=ft.ScrollMode.AUTO, height=700),
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

    def _open_start_date_picker(self, e):
        date_picker = ft.DatePicker(on_change=self._on_start_date_picked)
        self.page.overlay.append(date_picker)
        date_picker.open = True
        self.page.update()

    def _open_end_date_picker(self, e):
        date_picker = ft.DatePicker(on_change=self._on_end_date_picked)
        self.page.overlay.append(date_picker)
        date_picker.open = True
        self.page.update()

    def _clear_image(self):
        self.selected_image_path = None
        self.image_preview.content = ft.Icon(ft.Icons.IMAGE, size=48)
        self.image_preview.update()
        self.page.update()

    def _save_image(self, project_id: int) -> Optional[str]:
        if not self.selected_image_path or not Path(self.selected_image_path).exists():
            return None
        ext = Path(self.selected_image_path).suffix
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"project_{project_id}_{timestamp}{ext}"
        dest = IMAGES_DIR / filename
        import shutil
        shutil.copy2(self.selected_image_path, dest)
        return str(dest)

    def _delete_image(self, image_path: str):
        if image_path and Path(image_path).exists():
            try:
                Path(image_path).unlink()
            except:
                pass

    def _build_accounts_list(self, filter_text: str = ""):
        if not self.accounts_manager or not self.accounts_manager.accounts:
            self.accounts_list.controls = [ft.Text("No accounts available", color=ft.Colors.GREY_400)]
            return

        checkboxes = []
        filter_text = filter_text.lower()
        network = self.network_radio.value if self.network_radio else self.current_network

        for acc in self.accounts_manager.accounts:
            if network == NETWORK_EVM:
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

            network_label = "EVM" if network == NETWORK_EVM else "Solana"
            display = self._get_account_display(acc, network)
            label = f"{network_label} {acc['id']} ({display})"
            cb = ft.Checkbox(
                label=label,
                value=acc["id"] in self.current_project_accounts,
                data=acc["id"],
            )
            checkboxes.append(cb)

        self.accounts_list.controls = checkboxes if checkboxes else [ft.Text("No matching accounts", color=ft.Colors.GREY_400)]
        self.page.update()

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
            image_path = self._save_image(new_id) if self.selected_image_path else None
            new_project = {
                "id": new_id,
                "name": name,
                "description": self.desc_field.value,
                "status": self.status_dropdown.value,
                "type": self.type_dropdown.value,
                "network": self.network_radio.value,
                "start_date": self.start_field.value,
                "end_date": self.end_field.value,
                "accounts": selected_accounts,
                "image_path": image_path,
                "archived": False,
            }
            self.projects.append(new_project)
        else:
            # Сохраняем новое изображение, если выбрано
            new_image = None
            if self.selected_image_path:
                # Удаляем старое, если есть
                old_image = None
                for p in self.projects:
                    if p["id"] == self.editing_project_id:
                        old_image = p.get("image_path")
                        break
                if old_image:
                    self._delete_image(old_image)
                new_image = self._save_image(self.editing_project_id)
            for proj in self.projects:
                if proj["id"] == self.editing_project_id:
                    proj.update({
                        "name": name,
                        "description": self.desc_field.value,
                        "status": self.status_dropdown.value,
                        "type": self.type_dropdown.value,
                        "network": self.network_radio.value,
                        "start_date": self.start_field.value,
                        "end_date": self.end_field.value,
                        "accounts": selected_accounts,
                        "image_path": new_image if new_image is not None else proj.get("image_path"),
                    })
                    break

        save_projects(self.projects)
        self.close_dialog()
        self.update_content(self.get_view())

    # ---------- Архивация ----------
    def toggle_archive(self, e: ft.ControlEvent):
        project_id = e.control.data
        for proj in self.projects:
            if proj["id"] == project_id:
                proj["archived"] = not proj.get("archived", False)
                break
        save_projects(self.projects)
        self.update_content(self.get_view())

    # ---------- Подтверждение удаления ----------
    def _confirm_delete(self, project_id):
        def close_dialog(e):
            dlg.open = False
            self.page.update()

        def confirm(e):
            # Удаляем изображение перед удалением проекта
            for p in self.projects:
                if p["id"] == project_id:
                    if p.get("image_path"):
                        self._delete_image(p["image_path"])
                    break
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
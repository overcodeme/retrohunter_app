import flet as ft
import json
import datetime
import shutil
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from accounts import AccountsManager

# ──────────────────────────────────────────────────────────────────────────────
# Константы и утилиты
# ──────────────────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
PROJECTS_FILE = DATA_DIR / "projects.json"
IMAGES_DIR = DATA_DIR / "images"

NETWORK_EVM = "EVM"
NETWORK_SOLANA = "Solana"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)


def load_projects() -> List[Dict[str, Any]]:
    """Читает файл с проектами, создаёт его при отсутствии."""
    ensure_data_dir()
    if not PROJECTS_FILE.exists():
        with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []

    with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for proj in data:
        proj.setdefault("network", NETWORK_EVM)
        proj.setdefault("image_path", None)

    return data


def save_projects(projects: List[Dict[str, Any]]) -> None:
    """Записывает список проектов в JSON‑файл."""
    ensure_data_dir()
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(projects, f, indent=4, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Основной класс‑менеджер
# ──────────────────────────────────────────────────────────────────────────────
class ProjectsManager:
    def __init__(
        self,
        page: ft.Page,
        update_content_callback,
        accounts_manager: AccountsManager,
    ):
        self.page = page
        self.update_content = update_content_callback
        self.accounts_manager = accounts_manager
        self.expenses_manager = None
        self.projects = load_projects()

        # UI‑элементы диалога
        self.name_field: Optional[ft.TextField] = None
        self.desc_field: Optional[ft.TextField] = None
        self.status_dropdown: Optional[ft.Dropdown] = None
        self.type_dropdown: Optional[ft.Dropdown] = None
        self.start_field: Optional[ft.TextField] = None
        self.end_field: Optional[ft.TextField] = None
        self.search_field: Optional[ft.TextField] = None
        self.accounts_list: Optional[ft.Column] = None
        self.dialog_modal: Optional[ft.AlertDialog] = None
        self.editing_project_id: Optional[int] = None
        self.current_project_accounts: List[int] = []

        # Выбор сети и изображения
        self.network_radio: Optional[ft.RadioGroup] = None
        self.current_network = NETWORK_EVM
        self.image_preview: Optional[ft.Container] = None
        self.selected_image_path: Optional[str] = None
        self.file_picker: Optional[ft.FilePicker] = None
        self.image_cleared: bool = False                     # <<< NEW >>> флаг очистки

        # Фильтры
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

    # --------------------------------------------------------------------- #
    #  Вспомогательные методы
    # --------------------------------------------------------------------- #
    def set_expenses_manager(self, expenses_manager) -> None:
        self.expenses_manager = expenses_manager

    def _format_tooltip(self, text: str, max_chars: int = 50) -> str:
        if not text:
            return text
        words = text.split()
        lines, cur = [], ""
        for w in words:
            if len(cur) + len(w) + 1 <= max_chars:
                cur = f"{cur} {w}".strip()
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return "\n".join(lines)

    def _get_project_finances(self, project_id: int) -> tuple[float, float]:
        expenses, incomes = 0.0, 0.0
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
        return {
            "active": ft.Colors.GREEN_400,
            "waiting": ft.Colors.ORANGE_400,
            "completed": ft.Colors.BLUE_400,
            "cancelled": ft.Colors.GREY_400,
        }.get(status, ft.Colors.GREY_400)

    def _get_account_display(self, acc: Dict, network: str) -> str:
        if network == NETWORK_EVM:
            address = acc.get("evm_address")
            if address:
                return f"{address[:4]}...{address[-4:]}"
            key = acc.get("evm_private_key", "")
            return f"{key[:4]}...{key[-4:]}" if key else "No EVM"
        else:
            address = acc.get("solana_address")
            if address:
                return f"{address[:4]}...{address[-4:]}"
            key = acc.get("sol_private_key", "")
            return f"{key[:4]}...{key[-4:]}" if key else "No Solana"

    def _matches_filters(self, project: Dict) -> bool:
        if self.filter_search.value:
            txt = self.filter_search.value.lower()
            if not (
                txt in project.get("name", "").lower()
                or txt in project.get("description", "").lower()
                or txt in project.get("type", "").lower()
            ):
                return False
        if self.filter_type.value != "all" and project.get("type") != self.filter_type.value:
            return False
        if self.filter_status.value != "all" and project.get("status") != self.filter_status.value:
            return False
        if self.filter_expense.value != "all":
            expenses, incomes = self._get_project_finances(project["id"])
            total = expenses + incomes
            if self.filter_expense.value == "with" and total == 0:
                return False
            if self.filter_expense.value == "without" and total > 0:
                return False
        return True

    # --------------------------------------------------------------------- #
    #  Карточка проекта
    # --------------------------------------------------------------------- #
    def _build_project_card(self, project: Dict) -> ft.Container:
        project_id = project["id"]
        name = project.get("name", "")
        description = project.get("description", "")
        proj_type = project.get("type", "other").capitalize()
        status = project.get("status", "unknown")
        network = project.get("network", NETWORK_EVM)
        start = project.get("start_date", "")
        end = project.get("end_date", "")
        accounts_cnt = len(project.get("accounts", []))
        expenses, incomes = self._get_project_finances(project_id)

        status_color = self._get_status_color(status)

        image_path = project.get("image_path")
        if image_path and os.path.exists(image_path):
            avatar = ft.Container(
                content=ft.Image(src=image_path, fit=ft.BoxFit.COVER),
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
                alignment=ft.Alignment.CENTER,
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

        progress_value: Optional[float] = None
        if start and end:
            try:
                start_dt = datetime.datetime.strptime(start, "%Y-%m-%d")
                end_dt = datetime.datetime.strptime(end, "%Y-%m-%d")
                now = datetime.datetime.now()
                if now < start_dt:
                    progress_value = 0.0
                elif now > end_dt:
                    progress_value = 1.0
                else:
                    total = (end_dt - start_dt).days
                    passed = (now - start_dt).days
                    if total > 0:
                        progress_value = passed / total
            except Exception:
                progress_value = None

        short_desc = description[:80] + ("…" if len(description) > 80 else "")
        tooltip_desc = self._format_tooltip(description, 50)

        finance_row = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TRENDING_DOWN, size=14, color=ft.Colors.RED_400),
                        ft.Text(f"-${expenses:.2f}", size=14, color=ft.Colors.RED_400,
                                weight=ft.FontWeight.BOLD),
                    ],
                    spacing=5,
                )
                if expenses > 0
                else ft.Container(),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TRENDING_UP, size=14, color=ft.Colors.GREEN_400),
                        ft.Text(f"+${incomes:.2f}", size=14, color=ft.Colors.GREEN_400,
                                weight=ft.FontWeight.BOLD),
                    ],
                    spacing=5,
                )
                if incomes > 0
                else ft.Container(),
            ],
            spacing=2,
        )

        card_content = ft.Column(
            [
                ft.Row(
                    [
                        avatar,
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Container(width=12, height=12,
                                                     bgcolor=status_color,
                                                     border_radius=6),
                                        ft.Text(name, size=18,
                                                weight=ft.FontWeight.BOLD, expand=True),
                                        edit_btn,
                                        delete_btn,
                                    ],
                                    alignment=ft.MainAxisAlignment.START,
                                ),
                                ft.Text(
                                    short_desc,
                                    size=13,
                                    color=ft.Colors.GREY_400,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    tooltip=tooltip_desc,
                                )
                                if description
                                else ft.Container(),
                            ],
                            expand=True,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Divider(height=10, color=ft.Colors.GREY_800),
                ft.Row([ft.Icon(ft.Icons.LABEL_OUTLINE, size=14, color=ft.Colors.GREY_400),
                        ft.Text(proj_type, size=14)], spacing=5),
                ft.Row([ft.Icon(ft.Icons.DNS_OUTLINED, size=14, color=ft.Colors.GREY_400),
                        ft.Text(network, size=14)], spacing=5),
                ft.Row([ft.Icon(ft.Icons.CALENDAR_TODAY, size=14, color=ft.Colors.GREY_400),
                        ft.Text(f"{start} - {end}", size=14)], spacing=5),
                ft.Row([ft.Icon(ft.Icons.PEOPLE_OUTLINE, size=14, color=ft.Colors.GREY_400),
                        ft.Text(f"{accounts_cnt} accounts", size=14),
                        ft.Container(expand=True)], spacing=5),
                finance_row,
                ft.Container(height=5),
                ft.ProgressBar(
                    value=progress_value,
                    color=status_color,
                    bgcolor=ft.Colors.GREY_800,
                    height=6,
                    border_radius=3,
                )
                if progress_value is not None
                else ft.Container(),
            ]
        )

        return ft.Container(
            content=card_content,
            width=320,
            padding=15,
            border_radius=12,
            bgcolor=ft.Colors.GREY_900,
            shadow=ft.BoxShadow(
                blur_radius=10,
                color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
            ),
        )

    # --------------------------------------------------------------------- #
    #  Основное представление
    # --------------------------------------------------------------------- #
    def get_view(self) -> ft.Container:
        header = ft.Row(
            [
                ft.Text("Projects list", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.ElevatedButton(
                    "Add project",
                    icon=ft.Icons.ADD,
                    on_click=self.open_add_project_dialog,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE_600
                    ),
                ),
            ]
        )
        search_btn = ft.IconButton(
            icon=ft.Icons.SEARCH, tooltip="Search", on_click=self.apply_filters
        )
        search_row = ft.Row([self.filter_search, search_btn])
        filters_row = ft.Row(
            [self.filter_type, self.filter_status, self.filter_expense],
            spacing=10,
            wrap=True,
        )
        filtered = [p for p in self.projects if self._matches_filters(p)]
        stats_row = ft.Row(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.FOLDER_OUTLINED,
                                    size=20,
                                    color=ft.Colors.GREEN_400),
                            ft.Text(f"Projects: {len(filtered)} / {len(self.projects)}",
                                    size=16,
                                    weight=ft.FontWeight.W_500),
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
        if filtered:
            cards = [self._build_project_card(p) for p in filtered]
            projects_grid = ft.GridView(
                controls=cards,
                expand=True,
                runs_count=3,
                max_extent=350,
                spacing=10,
                run_spacing=10,
                padding=10,
            )
            grid_container = ft.Container(content=projects_grid, height=500)
        else:
            grid_container = ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.FOLDER_OUTLINED,
                                size=64,
                                color=ft.Colors.GREY_600),
                        ft.Text("No projects match your filters",
                                size=20,
                                color=ft.Colors.GREY_400),
                        ft.Text("Try adjusting search or filters",
                                color=ft.Colors.GREY_500),
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
                    search_row,
                    ft.Container(height=10),
                    filters_row,
                    ft.Container(height=10),
                    stats_row,
                    ft.Container(height=20),
                    grid_container,
                ]
            ),
            padding=20,
        )

    def apply_filters(self, e):
        self.update_content(self.get_view())

    # --------------------------------------------------------------------- #
    #  Диалог добавления / редактирования
    # --------------------------------------------------------------------- #
    def open_add_project_dialog(self, e: ft.ControlEvent = None):
        self.editing_project_id = None
        self.current_project_accounts = []
        self.current_network = NETWORK_EVM
        self.selected_image_path = None
        self.image_cleared = False                     # <<< NEW >>> сбрасываем флаг
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
            self.image_cleared = False                 # <<< NEW >>> сбрасываем флаг
            self._show_project_dialog(project)

    # --------------------------------------------------------------------- #
    #  Выбор изображения (новый async‑API)
    # --------------------------------------------------------------------- #
    async def _pick_image_async(self, e):
        file_picker = ft.FilePicker()
        self.page.services.append(file_picker)

        files = await file_picker.pick_files(
            allow_multiple=False,
            allowed_extensions=["png", "jpg", "jpeg", "gif"],
        )
        if files and len(files) > 0:
            picked = files[0]
            if picked.path:
                self.selected_image_path = picked.path
            elif picked.bytes:
                import tempfile
                ext = os.path.splitext(picked.name)[1] or ".png"
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(picked.bytes)
                    self.selected_image_path = tmp.name
            else:
                return

            # Пользователь выбрал новое изображение → сбрасываем флаг очистки
            self.image_cleared = False                # <<< NEW >>>
            if self.image_preview:
                self.image_preview.content = ft.Image(
                    src=self.selected_image_path,
                    fit=ft.BoxFit.COVER,
                )
                self.image_preview.update()
        self.page.update()

    def _clear_image(self):
        """Сбросить выбранное изображение."""
        self.selected_image_path = None
        self.image_cleared = True                     # <<< NEW >>> помечаем, что пользователь захотел удалить
        if self.image_preview:
            self.image_preview.content = ft.Icon(ft.Icons.IMAGE, size=48)
            self.image_preview.update()
        self.page.update()

    # --------------------------------------------------------------------- #
    #  Формирование диалога
    # --------------------------------------------------------------------- #
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
        self.network_radio = ft.RadioGroup(
            content=ft.Row(
                [
                    ft.Radio(value=NETWORK_EVM,
                             label="EVM",
                             fill_color=ft.Colors.BLUE_400),
                    ft.Radio(value=NETWORK_SOLANA,
                             label="Solana",
                             fill_color=ft.Colors.PURPLE_400),
                ]
            ),
            value=self.current_network,
            on_change=self.on_network_change,
        )

        # Кнопка выбора изображения
        choose_image_btn = ft.Button(
            content="Choose image",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._pick_image_async,
        )
        self.image_preview = ft.Container(
            content=ft.Image(src=self.selected_image_path,
                             fit=ft.BoxFit.COVER)
            if self.selected_image_path and os.path.exists(self.selected_image_path)
            else ft.Icon(ft.Icons.IMAGE, size=48),
            width=80,
            height=80,
            border_radius=40,
            bgcolor=ft.Colors.GREY_800,
            alignment=ft.Alignment.CENTER,
        )
        clear_image_btn = ft.IconButton(
            icon=ft.Icons.CLEAR,
            tooltip="Remove image",
            on_click=lambda _: self._clear_image(),
        )

        # Поиск аккаунтов
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
                content=ft.Column(
                    [
                        self.name_field,
                        self.desc_field,
                        ft.Row([self.status_dropdown, self.type_dropdown], spacing=10),
                        ft.Row([self.start_field, self.end_field], spacing=10),
                        ft.Divider(height=10, color=ft.Colors.GREY_800),
                        ft.Text("Project image:",
                                size=14,
                                weight=ft.FontWeight.BOLD),
                        ft.Row([choose_image_btn,
                                self.image_preview,
                                clear_image_btn],
                               spacing=10),
                        ft.Divider(height=10, color=ft.Colors.GREY_800),
                        ft.Text("Select accounts for this project:",
                                size=14,
                                weight=ft.FontWeight.BOLD),
                        self.network_radio,
                        ft.Row([select_all_btn, clear_all_btn],
                               alignment=ft.MainAxisAlignment.START),
                        self.search_field,
                        ft.Container(
                            content=self.accounts_list,
                            border=ft.Border.all(1, ft.Colors.GREY_800),
                            border_radius=5,
                            padding=10,
                            height=300,
                        ),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    height=700,
                ),
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

    # --------------------------------------------------------------------- #
    #  Сохранение / удаление изображений
    # --------------------------------------------------------------------- #
    def _save_image(self, project_id: int) -> Optional[str]:
        if not self.selected_image_path or not os.path.exists(self.selected_image_path):
            return None
        ext = os.path.splitext(self.selected_image_path)[1]
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"project_{project_id}_{ts}{ext}"
        dest = IMAGES_DIR / filename
        shutil.copy2(self.selected_image_path, dest)
        return str(dest)

    def _delete_image(self, image_path: str) -> None:
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception:
                pass

    # --------------------------------------------------------------------- #
    #  Список аккаунтов
    # --------------------------------------------------------------------- #
    def _build_accounts_list(self, filter_text: str = "") -> None:
        if not self.accounts_manager or not self.accounts_manager.accounts:
            self.accounts_list.controls = [
                ft.Text("No accounts available", color=ft.Colors.GREY_400)
            ]
            return

        checkboxes: List[ft.Checkbox] = []
        filter_text = filter_text.lower()
        network = (
            self.network_radio.value if self.network_radio else self.current_network
        )

        for acc in self.accounts_manager.accounts:
            if network == NETWORK_EVM:
                key = acc.get("evm_private_key", "")
                addr = acc.get("evm_address")
            else:
                key = acc.get("sol_private_key", "")
                addr = acc.get("solana_address")
            if not key:
                continue

            searchable = (
                f"id:{acc['id']} key:{key} addr:{addr or ''} email:{acc.get('email','')}"
            ).lower()
            if filter_text and filter_text not in searchable:
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

        self.accounts_list.controls = (
            checkboxes if checkboxes else [ft.Text("No matching accounts", color=ft.Colors.GREY_400)]
        )
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
        if self.dialog_modal:
            self.dialog_modal.open = False
            self.page.update()

    # --------------------------------------------------------------------- #
    #  Сохранение проекта
    # --------------------------------------------------------------------- #
    def save_project(self, e: ft.ControlEvent = None):
        name = self.name_field.value.strip()
        if not name:
            return

        selected_accounts = [
            cb.data
            for cb in self.accounts_list.controls
            if isinstance(cb, ft.Checkbox) and cb.value
        ]

        # ---------- Новый проект ----------
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
            }
            self.projects.append(new_project)

        # ---------- Обновление существующего ----------
        else:
            # По умолчанию оставляем старый путь
            new_image_path: Optional[str] = None

            # Если пользователь выбрал новое изображение
            if self.selected_image_path:
                # Удаляем старое (если есть)
                old_path = None
                for p in self.projects:
                    if p["id"] == self.editing_project_id:
                        old_path = p.get("image_path")
                        break
                if old_path:
                    self._delete_image(old_path)
                new_image_path = self._save_image(self.editing_project_id)

            # Если пользователь **очистил** изображение
            elif self.image_cleared:
                # Удаляем старое изображение (если есть)
                old_path = None
                for p in self.projects:
                    if p["id"] == self.editing_project_id:
                        old_path = p.get("image_path")
                        break
                if old_path:
                    self._delete_image(old_path)
                new_image_path = None                       # <-- явно ставим None

            # Обновляем проект
            for proj in self.projects:
                if proj["id"] == self.editing_project_id:
                    proj.update(
                        {
                            "name": name,
                            "description": self.desc_field.value,
                            "status": self.status_dropdown.value,
                            "type": self.type_dropdown.value,
                            "network": self.network_radio.value,
                            "start_date": self.start_field.value,
                            "end_date": self.end_field.value,
                            "accounts": selected_accounts,
                            "image_path": new_image_path
                            if (new_image_path is not None or self.image_cleared)
                            else proj.get("image_path"),
                        }
                    )
                    break

        save_projects(self.projects)

        # Сбрасываем флаг очистки, чтобы последующие операции не «запомнили» удаление
        self.image_cleared = False                     # <<< NEW >>>
        self.close_dialog()
        self.update_content(self.get_view())

    # --------------------------------------------------------------------- #
    #  Удаление проекта (подтверждение)
    # --------------------------------------------------------------------- #
    def _confirm_delete(self, project_id: int):
        def close_dialog(e):
            dlg.open = False
            self.page.update()

        def confirm(e):
            for p in self.projects:
                if p["id"] == project_id and p.get("image_path"):
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
                ft.ElevatedButton(
                    "Delete", on_click=confirm, color=ft.Colors.RED_400
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def _delete_project(self, project_id: int):
        self.projects = [p for p in self.projects if p["id"] != project_id]
        save_projects(self.projects)
        self.update_content(self.get_view())

    def delete_project(self, e: ft.ControlEvent):
        project_id = e.control.data
        self._confirm_delete(project_id)

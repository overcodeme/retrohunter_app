import flet as ft
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

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
    def __init__(self, page: ft.Page, update_content_callback, accounts_manager):
        self.page = page
        self.update_content = update_content_callback
        self.accounts_manager = accounts_manager  # для получения списка аккаунтов
        self.projects = load_projects()

        # Поля для диалога добавления/редактирования проекта
        self.name_field = None
        self.desc_field = None
        self.start_field = None
        self.end_field = None
        self.project_type = None
        self.status = None
        self.accounts_checkboxes = []  # список чекбоксов для выбора аккаунтов
        self.dialog_modal = None
        self.editing_project_id = None  # для редактирования

    def get_view(self) -> ft.Container:
        """Возвращает представление раздела проектов"""
        header = ft.Row([
            ft.Text("Projects management", size=24, weight=ft.FontWeight.BOLD),
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

        # Статистика: количество проектов
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
        ], alignment=ft.MainAxisAlignment.END)

        # Таблица проектов
        projects_table = self._create_projects_table()

        return ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=20, color=ft.Colors.GREY_800),
                stats_row,
                ft.Container(height=20),
                ft.Text("Projects list", size=18, weight=ft.FontWeight.BOLD),
                projects_table
            ]),
            padding=20
        )

    def _create_projects_table(self) -> ft.Container:
        """Создает таблицу со списком проектов"""
        if not self.projects:
            return ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.FOLDER_OUTLINED, size=64, color=ft.Colors.GREY_600),
                    ft.Text("No projects yet", size=20, color=ft.Colors.GREY_400),
                    ft.Text("Click 'Add project' to add a project", color=ft.Colors.GREY_500),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=50,
                alignment=ft.Alignment.CENTER,
                height=400,
            )

        rows = []
        for proj in self.projects:
            # Кнопки действий
            edit_btn = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                icon_color=ft.Colors.BLUE_400,
                tooltip="Edit project",
                data=proj.get("id"),
                on_click=self.open_edit_project_dialog
            )
            delete_btn = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                tooltip="Delete project",
                data=proj.get("id"),
                on_click=self.delete_project
            )

            # Формируем строку
            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(proj.get("id", "")), size=12)),
                    ft.DataCell(ft.Text(proj.get("name", ""), size=12, weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(proj.get("description", ""), size=12, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, width=200)),
                    ft.DataCell(ft.Text(proj.get("start_date", ""), size=12)),
                    ft.DataCell(ft.Text(proj.get("end_date", ""), size=12)),
                    ft.DataCell(ft.Text(str(len(proj.get("accounts", []))), size=12)),  # количество аккаунтов
                    ft.DataCell(ft.Row([edit_btn, delete_btn], spacing=5)),
                ]
            )
            rows.append(row)

        # Таблица с прокруткой
        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", size=12)),
                ft.DataColumn(ft.Text("Name", size=12)),
                ft.DataColumn(ft.Text("Description", size=12)),
                ft.DataColumn(ft.Text("Start", size=12)),
                ft.DataColumn(ft.Text("End", size=12)),
                ft.DataColumn(ft.Text("# Acc", size=12)),
                ft.DataColumn(ft.Text("Actions", size=12)),
            ],
            rows=rows,
            border=ft.Border.all(1, ft.Colors.GREY_800),
            vertical_lines=ft.BorderSide(1, ft.Colors.GREY_800),
            horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_800),
            column_spacing=15,
        )

        # Оборачиваем в контейнер с горизонтальной прокруткой
        return ft.Container(
            content=ft.Row([table], scroll=ft.ScrollMode.ALWAYS),
            height=400,
        )

    def open_add_project_dialog(self, e: ft.ControlEvent = None):
        """Открывает диалог создания нового проекта"""
        self.editing_project_id = None
        self._show_project_dialog()

    def open_edit_project_dialog(self, e: ft.ControlEvent):
        """Открывает диалог редактирования проекта"""
        project_id = e.control.data
        self.editing_project_id = project_id
        # Находим проект по id
        project = next((p for p in self.projects if p["id"] == project_id), None)
        if project:
            self._show_project_dialog(project)

    def _show_project_dialog(self, project: Optional[Dict] = None):
        """Показывает диалог добавления/редактирования проекта"""
        # Поля ввода
        self.name_field = ft.TextField(
            label="Project Name",
            value=project.get("name") if project else "",
            multiline=False,
        )
        self.desc_field = ft.TextField(
            label="Description",
            value=project.get("description") if project else "",
            multiline=True,
            min_lines=2,
            max_lines=4,
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

        # Создаем список чекбоксов для выбора аккаунтов
        self.accounts_checkboxes = []
        if self.accounts_manager and self.accounts_manager.accounts:
            for acc in self.accounts_manager.accounts:
                cb = ft.Checkbox(
                    label=f"ID {acc['id']}: {acc.get('email', 'No email')[:30]}",
                    value=acc["id"] in project.get("accounts", []) if project else False,
                    data=acc["id"],
                )
                self.accounts_checkboxes.append(cb)

        # Диалог
        self.dialog_modal = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Project" if project else "Add New Project"),
            content=ft.Container(
                content=ft.Column([
                    self.name_field,
                    self.desc_field,
                    ft.Row([self.start_field, self.end_field], spacing=10),
                    ft.Text("Select accounts for this project:", size=14, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=ft.Column(
                            self.accounts_checkboxes,
                            scroll=ft.ScrollMode.AUTO,
                            height=200,
                        ),
                        border=ft.Border.all(1, ft.Colors.GREY_800),
                        border_radius=5,
                        padding=10,
                    ) if self.accounts_checkboxes else ft.Text("No accounts available", color=ft.Colors.GREY_400),
                ], scroll=ft.ScrollMode.AUTO, height=500),
                width=600,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self.close_dialog),
                ft.ElevatedButton("Save", on_click=self.save_project),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.dialog = self.dialog_modal
        self.dialog_modal.open = True
        self.page.update()

    def close_dialog(self, e: ft.ControlEvent = None):
        self.dialog_modal.open = False
        self.page.update()

    def save_project(self, e: ft.ControlEvent = None):
        """Сохраняет проект (новый или обновленный)"""
        # Собираем данные
        name = self.name_field.value.strip()
        if not name:
            # Можно показать ошибку, но пока просто вернемся
            return

        # Получаем выбранные аккаунты
        selected_accounts = [
            cb.data for cb in self.accounts_checkboxes if cb.value
        ]

        if self.editing_project_id is None:
            # Новый проект
            new_id = max([p["id"] for p in self.projects], default=0) + 1
            new_project = {
                "id": new_id,
                "name": name,
                "description": self.desc_field.value,
                "start_date": self.start_field.value,
                "end_date": self.end_field.value,
                "accounts": selected_accounts,
            }
            self.projects.append(new_project)
        else:
            # Обновляем существующий
            for proj in self.projects:
                if proj["id"] == self.editing_project_id:
                    proj.update({
                        "name": name,
                        "description": self.desc_field.value,
                        "start_date": self.start_field.value,
                        "end_date": self.end_field.value,
                        "accounts": selected_accounts,
                    })
                    break

        save_projects(self.projects)
        self.close_dialog()
        self.update_content(self.get_view())

    def delete_project(self, e: ft.ControlEvent):
        """Удаляет проект по ID"""
        project_id = e.control.data
        self.projects = [p for p in self.projects if p["id"] != project_id]
        save_projects(self.projects)
        self.update_content(self.get_view())
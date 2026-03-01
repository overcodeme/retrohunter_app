import flet as ft
from accounts import AccountsManager
from projects import ProjectsManager


def main(page: ft.Page):
    page.title = "Retro activities tracker"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.width = 1200
    page.height = 900

    def update_content_area(new_content: ft.Container):
        content_area.content = new_content
        page.update()

    # Создаем менеджеры
    accounts_manager = AccountsManager(page, update_content_area)
    projects_manager = ProjectsManager(page, update_content_area, accounts_manager)

    def on_menu_click(e: ft.ControlEvent):
        for item in menu_items:
            item.bgcolor = None
            

        if e.control.data == "wallets":
            content_area.content = accounts_manager.get_view()
        elif e.control.data == "projects":
            content_area.content = projects_manager.get_view()
        elif e.control.data == "expenses":
            content_area.content = expenses_view()
        elif e.control.data == "stats":
            content_area.content = stats_view()

        page.update()

    # Заглушки для других разделов
    def expenses_view():
        return ft.Container(
            content=ft.Column([
                ft.Text("Expenses management", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("Here will be expenses list", color=ft.Colors.GREY_400)
            ]),
            padding=20
        )

    def stats_view():
        return ft.Container(
            content=ft.Column([
                ft.Text("Statistics", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("Here will be statistics", color=ft.Colors.GREY_400)
            ]),
            padding=20
        )

    # Пункты меню
    menu_items = [
        ft.Container(
            content=ft.Text("Wallets", size=16),
            data="wallets",
            padding=15,
            border_radius=10,
            on_click=on_menu_click
        ),
        ft.Container(
            content=ft.Text("Projects", size=16),
            data="projects",
            padding=15,
            border_radius=10,
            on_click=on_menu_click
        ),
        ft.Container(
            content=ft.Text("Expenses", size=16),
            data="expenses",
            padding=15,
            border_radius=10,
            on_click=on_menu_click
        ),
        ft.Container(
            content=ft.Text("Statistics", size=16),
            data="stats",
            padding=15,
            border_radius=10,
            on_click=on_menu_click
        )
    ]

    content_area = ft.Container(
        content=accounts_manager.get_view(),
        expand=True
    )

    # Подсвечиваем первый пункт меню
    menu_items[0].bgcolor = ft.Colors.BLUE_GREY_700

    page.add(
        ft.Row([
            ft.Container(
                content=ft.Column(
                    menu_items,
                    spacing=5
                ),
                width=200,
                padding=10,
                border=ft.Border.all(1, ft.Colors.GREY_800)
            ),
            content_area
        ],
        expand=True,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH
        )
    )

    page.update()


if __name__ == "__main__":
    ft.run(main)
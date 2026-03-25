import flet as ft
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from collections import defaultdict
import numpy as np

class DashboardManager:
    def __init__(self, page: ft.Page, accounts_manager, projects_manager, expenses_manager):
        self.page = page
        self.accounts_manager = accounts_manager
        self.projects_manager = projects_manager
        self.expenses_manager = expenses_manager

    @staticmethod
    def _bytesio_to_data_url(buf: io.BytesIO, mime: str = "image/png") -> str:
        raw = buf.getvalue()
        b64 = base64.b64encode(raw).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def get_view(self) -> ft.Container:
        total_accounts = len(self.accounts_manager.accounts)
        total_projects = len(self.projects_manager.projects)

        expenses = []
        incomes = []
        for exp in self.expenses_manager.expenses:
            amount = exp.get("amount", 0)
            if exp.get("type") == "expense":
                expenses.append(amount)
            else:
                incomes.append(amount)
        total_expenses = sum(expenses)
        total_incomes = sum(incomes)
        balance = total_incomes - total_expenses

        monthly_data = defaultdict(lambda: {"expenses": 0, "incomes": 0})
        for exp in self.expenses_manager.expenses:
            date_str = exp.get("date", "")
            if date_str and len(date_str) >= 7:
                year_month = date_str[:7]
                amount = exp.get("amount", 0)
                if exp.get("type") == "expense":
                    monthly_data[year_month]["expenses"] += amount
                else:
                    monthly_data[year_month]["incomes"] += amount

        months = sorted(monthly_data.keys())
        expenses_by_month = [monthly_data[m]["expenses"] for m in months]
        incomes_by_month = [monthly_data[m]["incomes"] for m in months]

        fig1, ax1 = plt.subplots(figsize=(8, 4))
        x = np.arange(len(months))
        width_bar = 0.35
        ax1.bar(x - width_bar/2, expenses_by_month, width_bar, label='Expenses', color='red')
        ax1.bar(x + width_bar/2, incomes_by_month, width_bar, label='Incomes', color='green')
        ax1.set_xlabel('Month')
        ax1.set_ylabel('Amount (USD)')
        ax1.set_title('Expenses & Incomes by Month')
        ax1.set_xticks(x)
        ax1.set_xticklabels(months, rotation=45, ha='right')
        ax1.legend()
        plt.tight_layout()

        buf1 = io.BytesIO()
        plt.savefig(buf1, format='png')
        buf1.seek(0)
        plt.close(fig1)

        img1_src = self._bytesio_to_data_url(buf1)

        category_expenses = defaultdict(float)
        for exp in self.expenses_manager.expenses:
            if exp.get("type") == "expense":
                cat = exp.get("category", "Other")
                category_expenses[cat] += exp.get("amount", 0)

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

        stats_row = ft.Row([
            ft.Container(
                content=ft.Column([
                    ft.Text("Total Accounts", size=14, color=ft.Colors.GREY_400),
                    ft.Text(str(total_accounts), size=28, weight=ft.FontWeight.BOLD),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=15,
                bgcolor=ft.Colors.GREY_900,
                border_radius=10,
                expand=True,
                alignment=ft.Alignment.CENTER,
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Total Projects", size=14, color=ft.Colors.GREY_400),
                    ft.Text(str(total_projects), size=28, weight=ft.FontWeight.BOLD),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=15,
                bgcolor=ft.Colors.GREY_900,
                border_radius=10,
                expand=True,
                alignment=ft.Alignment.CENTER,
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Total Expenses", size=14, color=ft.Colors.GREY_400),
                    ft.Text(f"${total_expenses:.2f}", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=15,
                bgcolor=ft.Colors.GREY_900,
                border_radius=10,
                expand=True,
                alignment=ft.Alignment.CENTER,
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Total Incomes", size=14, color=ft.Colors.GREY_400),
                    ft.Text(f"${total_incomes:.2f}", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=15,
                bgcolor=ft.Colors.GREY_900,
                border_radius=10,
                expand=True,
                alignment=ft.Alignment.CENTER,
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text("Balance", size=14, color=ft.Colors.GREY_400),
                    ft.Text(f"${balance:.2f}", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400 if balance >= 0 else ft.Colors.RED_400),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=15,
                bgcolor=ft.Colors.GREY_900,
                border_radius=10,
                expand=True,
                alignment=ft.Alignment.CENTER,
            ),
        ], spacing=10)

        chart1 = ft.Container(
            content=ft.Image(src=img1_src, fit=ft.BoxFit.CONTAIN),
            border=ft.Border.all(1, ft.Colors.GREY_800),
            border_radius=10,
            padding=10,
            margin=ft.margin.only(bottom=10),
            expand=True,
        )

        if img2_src:
            chart2 = ft.Container(
                content=ft.Image(src=img2_src, fit=ft.BoxFit.CONTAIN),
                border=ft.Border.all(1, ft.Colors.GREY_800),
                border_radius=10,
                padding=10,
                expand=True,
            )
        else:
            chart2 = ft.Container(
                content=ft.Text("No expense data for categories", color=ft.Colors.GREY_400),
                border=ft.Border.all(1, ft.Colors.GREY_800),
                border_radius=10,
                padding=10,
                alignment=ft.Alignment.CENTER,
                expand=True,
            )

        charts_row = ft.Row([chart1, chart2], spacing=10, expand=True)

        return ft.Container(
            content=ft.Column([
                ft.Text("Dashboard", size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(height=20, color=ft.Colors.GREY_800),
                stats_row,
                ft.Container(height=20),
                charts_row,
            ]),
            padding=20,
        )

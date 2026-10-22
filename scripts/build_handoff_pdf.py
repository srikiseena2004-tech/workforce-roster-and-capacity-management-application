"""One-off handoff PDF: workflow and demo logins."""

from fpdf import FPDF
from fpdf.enums import XPos, YPos

OUT = r"c:\Users\seena\rta_project\Workforce_Roster_Workflow.pdf"

TEAL = (13, 92, 86)
DARK = (8, 63, 59)
INK = (28, 36, 48)
MUTED = (90, 98, 94)
RULE = (210, 200, 186)
HEAD_BG = (232, 242, 240)
ROW_ALT = (248, 245, 239)

TEAMS = ["Alpha", "Bravo", "Charlie", "Delta"]


def agents():
    rows = []
    for number in range(1, 41):
        agent_id = f"AGT{number:03d}"
        lead_index = (number - 1) // 10
        rows.append(
            (
                agent_id,
                f"Agent {number}",
                TEAMS[(number - 1) % 4],
                f"Team Lead {lead_index + 1}",
                "demo123",
            )
        )
    return rows


class Handout(FPDF):
    def header(self):
        self.set_fill_color(*DARK)
        self.rect(0, 0, 210, 16, "F")
        self.set_xy(12, 4.5)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(255, 255, 255)
        self.cell(140, 7, "Workforce roster and capacity", new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 9)
        self.cell(46, 7, "November 2026", align="R")
        self.set_text_color(*INK)
        self.set_y(22)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"Demo access  |  Page {self.page_no()} of {{nb}}", align="C")


def heading(pdf: Handout, text: str):
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*TEAL)
    pdf.cell(0, 8, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*TEAL)
    pdf.set_line_width(0.4)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(3)
    pdf.set_text_color(*INK)


def body(pdf: Handout, text: str):
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 5.2, text)
    pdf.ln(1.5)


def step(pdf: Handout, number: str, title: str, detail: str):
    y = pdf.get_y()
    if y > 250:
        pdf.add_page()
        y = pdf.get_y()
    pdf.set_fill_color(*TEAL)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(12, y)
    pdf.cell(8, 8, number, align="C", fill=True)
    pdf.set_xy(23, y)
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.cell(0, 5, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(23)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(55, 62, 58)
    pdf.multi_cell(173, 4.8, detail)
    pdf.ln(2.2)


def _table_header(pdf: Handout, headers, widths):
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(*HEAD_BG)
    pdf.set_text_color(*DARK)
    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.2)
    for header, width in zip(headers, widths):
        pdf.cell(width, 7, header, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*INK)


def table(pdf: Handout, headers, rows, widths):
    if pdf.get_y() + 7 + 6.2 > 272:
        pdf.add_page()
    _table_header(pdf, headers, widths)
    for index, row in enumerate(rows):
        if pdf.get_y() + 6.2 > 272:
            pdf.add_page()
            _table_header(pdf, headers, widths)
        if index % 2 == 1:
            pdf.set_fill_color(*ROW_ALT)
            fill = True
        else:
            fill = False
        for value, width in zip(row, widths):
            pdf.cell(width, 6.2, value, border=1, fill=fill)
        pdf.ln()
    pdf.ln(2)


def main():
    pdf = Handout(format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_left_margin(12)
    pdf.set_right_margin(12)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*INK)
    pdf.cell(0, 9, "Workflow and sign-in", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        0,
        5,
        "Attach this note with the workforce roster site. Every account uses the same demo password.",
    )
    pdf.ln(1)

    heading(pdf, "1. Open the site")
    body(
        pdf,
        "Local demo: http://localhost:5173\n"
        "Single-server deploy (Docker): http://localhost:8000\n"
        "Password for every account below: demo123",
    )

    heading(pdf, "2. Workflow")
    body(
        pdf,
        "The site covers 1-30 November 2026 for 40 agents. Team Leads record attendance. "
        "RTA changes who is scheduled to work. Agents can open only their own record. "
        "The daily surplus is calculated from the roster.",
    )
    step(
        pdf,
        "1",
        "Sign in",
        "Use a username from the tables below and the password demo123. The header shows RTA, the Team Lead name, or the agent id. Sign out is on the right.",
    )
    step(
        pdf,
        "2",
        "Daily dashboard",
        "Pick a date. The tiles show forecast volume, required agents, scheduled headcount, Present FTE, leave, capacity hours, and center surplus. Team, Team Lead, agent, and status filters change only the selected-group counts. The center surplus always uses all 40 agents.",
    )
    step(
        pdf,
        "3",
        "Monthly roster",
        "The month is shown one week at a time, Sunday to Saturday. Click a cell to open that day. Colors show the attendance status. Download the filtered roster as CSV from this page.",
    )
    step(
        pdf,
        "4",
        "Team Lead saves attendance",
        "tl1 to tl4 can update only their own 10 agents, and only on a Working day. Choices are Present, Sick Leave, BL, PL, Unplanned Leave, Comp Off, Floating Holiday, Special Leave, and NCNS. A leave can be a full day or a half day. NCNS and Unplanned Leave need a comment. A weekly off cannot be edited here.",
    )
    step(
        pdf,
        "5",
        "RTA changes the schedule",
        "Sign in as wfm. On a cell, change Working to Weekly Off, or Weekly Off to Working. RTA does not submit leave. Turning a weekly off into a working day sets that agent to Present.",
    )
    step(
        pdf,
        "6",
        "Agent reviews their own month",
        "Sign in with the agent id, for example AGT001. The page shows that agent's name, team, Team Lead, shift, present days, leave days, and weekly offs. The agent cannot change attendance.",
    )
    step(
        pdf,
        "7",
        "Charts and audit",
        "Charts are center-wide: required agents versus Present FTE, forecast volume, the attendance mix, and daily surplus. Audit lists each saved change with the previous value, the new value, who saved it, and the comment. It stays empty until the first save.",
    )
    step(
        pdf,
        "8",
        "Company demo on 2 November",
        "Sign in as tl1. Before any edit the day shows volume 890, required 26.4, scheduled 40, Present FTE 37, absent FTE 3, capacity 267.33 hours, surplus +10.6. Mark AGT001 as full-day Sick Leave. Scheduled stays 40, Present FTE becomes 36, and surplus becomes +9.6. Open Audit to show that row. Sign in as tl2 to show that AGT001 cannot be edited. Download the daily staffing report from the dashboard.",
    )

    if pdf.get_y() > 220:
        pdf.add_page()
    heading(pdf, "3. Staff logins")
    body(pdf, "Password for each row: demo123")
    table(
        pdf,
        ["Username", "Password", "Role", "Access"],
        [
            ("wfm", "demo123", "RTA", "Schedule Working or Weekly Off for all agents"),
            ("tl1", "demo123", "Team Lead 1", "Attendance for AGT001 to AGT010"),
            ("tl2", "demo123", "Team Lead 2", "Attendance for AGT011 to AGT020"),
            ("tl3", "demo123", "Team Lead 3", "Attendance for AGT021 to AGT030"),
            ("tl4", "demo123", "Team Lead 4", "Attendance for AGT031 to AGT040"),
        ],
        [32, 28, 36, 90],
    )

    heading(pdf, "4. Agent logins")
    body(
        pdf,
        "Username is the agent id. Password for every agent is demo123. "
        "Each Team Lead owns 10 agents, spread across Alpha, Bravo, Charlie, and Delta.",
    )
    table(
        pdf,
        ["Username", "Name", "Team", "Team Lead", "Password"],
        agents(),
        [32, 32, 32, 40, 50],
    )

    pdf.output(OUT)
    print(OUT)


if __name__ == "__main__":
    main()

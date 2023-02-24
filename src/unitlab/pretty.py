from datetime import datetime, timedelta, timezone

from prettytable.colortable import ColorTable, Themes


def fill_end(text, slice):
    return text[:slice] + "..." if text else text


def print_ai_model(data, many=False):
    table = ColorTable(theme=Themes.OCEAN)
    table.field_names = [
        "AI-Model ID",
        "Name",
        "Type",
    ]
    if many:
        for model in data:
            table.add_row(
                [
                    model["pk"],
                    model["name"],
                    model["data_type"],
                ]
            )
    else:
        table.add_row(
            [
                fill_end(data["pk"], 4),
                data["name"],
                data["data_type"],
            ]
        )
    print(table)


def print_task(data, many=False):
    table = ColorTable(theme=Themes.OCEAN)
    table.field_names = [
        "Task ID",
        "Name",
        "AI-Model",
        "# of Data",
        "Annotator Progress(%)",
        "Reviewer Progress(%)",
        "Creator",
        "Created Date",
        "Price",
    ]
    if many:
        for task in data:
            table.add_row(
                [
                    task["pk"],
                    fill_end(task["name"], 6),
                    fill_end(task["parent_name"], 6),
                    task["invoice"]["images"],
                    task["annotator_progress"],
                    task["reviewer_progress"],
                    task["creator"],
                    datetime.fromisoformat(task["created"])
                    .astimezone(datetime.now(timezone.utc).astimezone().tzinfo)
                    .strftime("%Y-%m-%d"),
                    task["invoice"]["price"],
                ]
            )
    else:
        table.add_row(
            [
                fill_end(data["pk"], 4),
                fill_end(data["name"], 6),
                fill_end(data["parent_name"], 6),
                data["invoice"]["images"],
                data["annotator_progress"],
                data["reviewer_progress"],
                data["creator"],
                datetime.fromisoformat(data["created"])
                .astimezone(datetime.now(timezone.utc).astimezone().tzinfo)
                .strftime("%Y-%m-%d"),
                data["invoice"]["price"],
            ]
        )
    print(table)


def print_data_sources(data):
    table = ColorTable(theme=Themes.OCEAN)
    table.field_names = [
        "Data Source ID",
        "Labeler Status",
        "Reviewer Status",
    ]
    for source in data:
        table.add_row(
            [
                source["pk"],
                source["status"] or "N/A",
                source["review_status"] or "N/A",
            ]
        )
    print(table)


def print_members(data):
    table = ColorTable(theme=Themes.OCEAN)
    table.field_names = [
        "Member ID",
        "Member Email",
        "Role",
        "Progress(%)",
        "Average Time",
        "Overall Time",
    ]
    for member in data:
        table.add_row(
            [
                member["worker"]["pk"],
                member["worker"]["email"],
                member["worker"]["role"],
                member["progress"],
                timedelta(seconds=member["average_time"]),
                timedelta(seconds=member["overall_time"]),
            ]
        )
    print(table)


def print_task_statistics(data):
    table = ColorTable(theme=Themes.OCEAN)
    table.field_names = [
        "# of Data",
        "Labeler Progress(%)",
        "Reviewer Progress(%)",
        "Labeler Average Time",
        "Reviewer Average Time",
        "Labeler Overall Time",
        "Reviewer Overall Time",
    ]
    table.add_row(
        [
            data["total_data"],
            data["labeler_progress"],
            data["reviewer_progress"],
            timedelta(seconds=data["labeler_average_time"]),
            timedelta(seconds=data["reviewer_average_time"]),
            timedelta(seconds=data["labeler_overall_time"]),
            timedelta(seconds=data["reviewer_overall_time"]),
        ]
    )

    print(table)

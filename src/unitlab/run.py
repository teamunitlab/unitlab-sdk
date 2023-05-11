import argparse

from . import core


def main():
    parser = argparse.ArgumentParser(
        prog="unitlab",
        description="Unitlab Inc. Python-SDK",
        allow_abbrev=False,
        epilog="For more information, please visit https://unitlab.ai",
    )
    subparsers = parser.add_subparsers(required=True)

    # Task List
    parser_task_list = subparsers.add_parser("tasks", help="Get task list")
    parser_task_list.add_argument("-k", "--api_key", **core.api_key_template)
    parser_task_list.set_defaults(func=core.task_list)

    # Task Detail
    parser_task_detail = subparsers.add_parser("task", help="Get task detail")
    parser_task_detail.add_argument(
        "-id", "--uuid", type=core.validate_uuid, required=True, help="Task uuid"
    )
    parser_task_detail.add_argument("-k", "--api_key", **core.api_key_template)
    parser_task_detail.set_defaults(func=core.task_detail)

    # Task DataSources
    parser_task_data_sources = subparsers.add_parser(
        "task-data", help="Get task's datasources"
    )
    parser_task_data_sources.add_argument(
        "-id", "--uuid", type=core.validate_uuid, required=True, help="Task uuid"
    )
    parser_task_data_sources.add_argument("-k", "--api_key", **core.api_key_template)
    parser_task_data_sources.set_defaults(func=core.task_data_sources)

    # Task Members
    parser_task_members = subparsers.add_parser(
        "task-members", help="Get task's members"
    )
    parser_task_members.add_argument(
        "-id", "--uuid", type=core.validate_uuid, required=True, help="Task uuid"
    )
    parser_task_members.add_argument("-k", "--api_key", **core.api_key_template)
    parser_task_members.set_defaults(func=core.task_members)

    # Task Statistics
    parser_task_statistics = subparsers.add_parser(
        "task-statistics", help="Get task's statistics"
    )
    parser_task_statistics.add_argument(
        "-id", "--uuid", type=core.validate_uuid, required=True, help="Task uuid"
    )
    parser_task_statistics.add_argument("-k", "--api_key", **core.api_key_template)
    parser_task_statistics.set_defaults(func=core.task_statistics)

    # Task Upload DataSources
    parser_task_upload_datasources = subparsers.add_parser(
        "upload-data", help="Upload task datasources"
    )
    parser_task_upload_datasources.add_argument(
        "-id", "--uuid", type=core.validate_uuid, required=True, help="Task uuid"
    )
    parser_task_upload_datasources.add_argument(
        "-i", "--input_dir", help="The input directory", required=True
    )
    parser_task_upload_datasources.add_argument(
        "-k", "--api_key", **core.api_key_template
    )
    parser_task_upload_datasources.set_defaults(func=core.task_upload_datasources)

    # Task Download Labeled Data
    parser_task_download_labeled_data = subparsers.add_parser(
        "download-data", help="Download task labeled data"
    )
    parser_task_download_labeled_data.add_argument(
        "-id", "--uuid", type=core.validate_uuid, required=True, help="Task uuid"
    )
    parser_task_download_labeled_data.add_argument(
        "-k", "--api_key", **core.api_key_template
    )
    parser_task_download_labeled_data.set_defaults(func=core.task_download_data)

    # DataSource Result
    parser_datasource_result = subparsers.add_parser(
        "datasource-result", help="Get datasource result"
    )
    parser_datasource_result.add_argument(
        "-id", "--uuid", type=core.validate_uuid, required=True, help="DataSource uuid"
    )
    parser_datasource_result.add_argument("-k", "--api_key", **core.api_key_template)
    parser_datasource_result.set_defaults(func=core.datasource_result)

    # AI Model List
    parser_ai_model_list = subparsers.add_parser(
        "ai-models", help="Get AI model list"
    )
    parser_ai_model_list.add_argument("-k", "--api_key", **core.api_key_template)
    parser_ai_model_list.set_defaults(func=core.ai_model_list)

    # AI Model Detail
    parser_ai_model_detail = subparsers.add_parser(
        "ai-model", help="Get AI model detail"
    )
    parser_ai_model_detail.add_argument(
        "-id", "--uuid", type=core.validate_uuid, required=True, help="AI model uuid"
    )
    parser_ai_model_detail.add_argument("-k", "--api_key", **core.api_key_template)
    parser_ai_model_detail.set_defaults(func=core.ai_model_detail)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

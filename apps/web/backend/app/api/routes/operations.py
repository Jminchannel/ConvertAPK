"""运行环境与系统查询路由。"""

from collections.abc import Callable

from fastapi import FastAPI


def register_operations_routes(
    app: FastAPI,
    *,
    get_queue_status: Callable,
    get_env_status: Callable,
    get_env_status_alt: Callable,
    get_env_config: Callable,
    get_env_config_alt: Callable,
    set_env_config: Callable,
    set_env_config_alt: Callable,
    prepare_env: Callable,
    prepare_env_alt: Callable,
    get_app_version: Callable,
    system_info: Callable,
    get_github_repo_stats: Callable,
    url_probe: Callable,
) -> None:
    """注册不依赖任务资源路径的运行与系统端点。"""
    app.add_api_route("/api/queue/status", get_queue_status, methods=["GET"])
    app.add_api_route("/api/env/status", get_env_status, methods=["GET"])
    app.add_api_route("/env/status", get_env_status_alt, methods=["GET"])
    app.add_api_route("/api/env/config", get_env_config, methods=["GET"])
    app.add_api_route("/env/config", get_env_config_alt, methods=["GET"])
    app.add_api_route("/api/env/config", set_env_config, methods=["POST"])
    app.add_api_route("/env/config", set_env_config_alt, methods=["POST"])
    app.add_api_route("/api/env/prepare", prepare_env, methods=["GET", "POST"])
    app.add_api_route("/env/prepare", prepare_env_alt, methods=["GET", "POST"])
    app.add_api_route("/api/app/version", get_app_version, methods=["GET"])
    app.add_api_route("/api/system/info", system_info, methods=["GET"])
    app.add_api_route("/api/github/repo-stats", get_github_repo_stats, methods=["GET"])
    app.add_api_route("/api/url-probe", url_probe, methods=["POST"])

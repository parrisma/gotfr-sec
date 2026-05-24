"""Basic import checks for the bootstrap package."""


def test_main_web_imports():
    from app import main_web

    assert callable(main_web.build_parser)
    assert callable(main_web.main)


def test_settings_imports():
    from app import settings

    assert settings.DEFAULT_MCP_PORT == 8060
    assert settings.DEFAULT_MCPO_PORT == 8061
    assert settings.DEFAULT_WEB_PORT == 8062


def test_web_server_imports():
    from app.web_server import GofrSecWebServer

    server = GofrSecWebServer(version="test")
    assert server.app.title == "gofr-sec"
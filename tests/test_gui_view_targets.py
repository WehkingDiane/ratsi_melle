from __future__ import annotations

from types import SimpleNamespace

from src.interfaces.gui.app import GuiLauncher


def test_activate_runtime_output_targets_switches_between_views() -> None:
    app = SimpleNamespace(
        data_tools_status_label=object(),
        data_tools_log_text=object(),
        data_tools_output_frame=object(),
        data_tools_right_title=object(),
        data_tools_right_content=object(),
        export_status_label=object(),
        export_log_text=object(),
        export_right_title=object(),
        export_right_content=object(),
        status_label=None,
        log_text=None,
        output_frame=None,
        right_title=None,
        right_content=None,
    )

    GuiLauncher._activate_runtime_output_targets(app, "analysis_export")

    assert app.status_label is app.export_status_label
    assert app.log_text is app.export_log_text
    assert app.right_title is app.export_right_title
    assert app.right_content is app.export_right_content
    assert app.output_frame is None

    GuiLauncher._activate_runtime_output_targets(app, "data_tools")

    assert app.status_label is app.data_tools_status_label
    assert app.log_text is app.data_tools_log_text
    assert app.output_frame is app.data_tools_output_frame
    assert app.right_title is app.data_tools_right_title
    assert app.right_content is app.data_tools_right_content

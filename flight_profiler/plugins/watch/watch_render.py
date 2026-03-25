from flight_profiler.plugins.watch.watch_displayer import WatchResult
from flight_profiler.utils.render_util import (
    BOX_HORIZONTAL,
    COLOR_BOLD,
    COLOR_END,
    COLOR_FAINT,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_WHITE_255,
    ICON_FAILED,
    ICON_SUCCESS,
    align_json_lines,
    align_prefix,
)
from flight_profiler.utils.time_util import time_ms_to_formatted_string


class WatchRender:

    def show_watch_result(self, result: WatchResult, output_raw: bool = False):
        title: str = self.__build_title(result)
        left_offset: int = 20
        if result.filter_fail_info is not None:
            value_str = (
                f"{COLOR_WHITE_255}  {'FILTER_EXPR:'.ljust(left_offset)}{align_prefix(left_offset + 2, result.filter_expr)}{COLOR_END}\n"
                f"{COLOR_WHITE_255}  {'FILTER_FAIL_INFO:'.ljust(left_offset)}{COLOR_END}"
                f"{COLOR_RED}{align_json_lines(left_offset + 2, result.filter_fail_info, True)}{COLOR_END}\n"
                f"{COLOR_WHITE_255}}}{COLOR_END}"
            )
            return f"{title}{value_str}"

        if result.watch_fail_info is not None:
            value_str = (
                f"{COLOR_WHITE_255}  {'EXPR:'.ljust(left_offset)}{align_prefix(left_offset + 2, result.expr)}{COLOR_END}\n"
                f"{COLOR_WHITE_255}  {'WATCH_FAIL_INFO:'.ljust(left_offset)}{COLOR_END}"
                f"{COLOR_RED}{align_json_lines(left_offset + 2, result.watch_fail_info, True)}{COLOR_END}\n"
            )
            if result.exception is not None:
                value_str += (
                    f"{COLOR_WHITE_255}  {'EXCEPTION:'.ljust(left_offset)}{COLOR_END}"
                    f"{COLOR_RED}{align_json_lines(left_offset + 2, result.exception, True)}{COLOR_END}\n"
                )
            value_str += f"{COLOR_WHITE_255}}}{COLOR_END}"
            return f"{title}{value_str}"

        if result.exception is None:
            left_offset = 8
        else:
            left_offset = 12
        value_str = (
            f"{COLOR_WHITE_255}  {'EXPR:'.ljust(left_offset)}{align_prefix(left_offset + 2, result.expr)}{COLOR_END}\n"
            f"{COLOR_WHITE_255}  {'TYPE:'.ljust(left_offset)}{align_prefix(left_offset + 2, result.type)}{COLOR_END}\n"
            f"{COLOR_WHITE_255}  {'VALUE:'.ljust(left_offset)}"
            f"{align_json_lines(left_offset + 2, result.value, split_internal_line=False)}{COLOR_END}\n"
        )
        if result.exception is not None:
            value_str += (
                f"{COLOR_WHITE_255}  {'EXCEPTION:'.ljust(left_offset)}{COLOR_END}"
                f"{COLOR_RED}{align_json_lines(left_offset + 2, result.exception, True)}{COLOR_END}\n"
            )
        value_str += f"{COLOR_WHITE_255}}}{COLOR_END}"
        return f"{title}{value_str}"

    def __build_title(self, result: WatchResult):
        formated_cost = "{:.6f}".format(result.cost_ms)
        status_icon = ICON_FAILED if result.is_exp else ICON_SUCCESS
        status_color = COLOR_RED if result.is_exp else COLOR_GREEN
        return (
            f"{COLOR_FAINT}{BOX_HORIZONTAL * 60}{COLOR_END}\n"
            f"{status_color}{status_icon}{COLOR_END} "
            f"{COLOR_WHITE_255}{time_ms_to_formatted_string(result.start_time)} "
            f"{COLOR_FAINT}method={COLOR_END}{result.method_identifier} "
            f"{COLOR_FAINT}cost={COLOR_END}{formated_cost}ms "
            f"{COLOR_FAINT}is_exp={COLOR_END}{COLOR_BOLD}{status_color}{result.is_exp}{COLOR_END}"
            f"{COLOR_WHITE_255} result={{{COLOR_END}\n"
        )

import pickle
import shutil
from typing import List

from flight_profiler.plugins.tt.time_tunnel_recorder import (
    BaseInvocationRecord,
    FullInvocationRecord,
)
from flight_profiler.utils.render_util import (
    BOX_HORIZONTAL,
    COLOR_BOLD,
    COLOR_END,
    COLOR_FAINT,
    COLOR_ORANGE,
    COLOR_WHITE_255,
    align_json_lines,
)
from flight_profiler.utils.time_util import time_ms_to_formatted_string


class TimeTunnelRender:

    def render_indexed_record(
        self, full_record: FullInvocationRecord
    ):
        left_item_offset: int = 20
        base_record = full_record.base_record
        cost_ms: str = "{:.7g}".format(base_record.cost_ms)
        args_str = align_json_lines(
            left_item_offset + 1,
            full_record.args,
            split_internal_line=False,
        )
        kwargs_str = align_json_lines(
            left_item_offset + 1,
            full_record.kwargs,
            split_internal_line=False,
        )
        return_obj = ""
        if base_record.is_ret:
            return_obj = (
                f"{COLOR_WHITE_255} {'RETURN_OBJ'.ljust(left_item_offset)}{COLOR_END}"
                f"{COLOR_ORANGE}{align_json_lines(left_item_offset + 1, full_record.return_obj, split_internal_line=False)}{COLOR_END}\n"
            )
        exception_msg = ""
        if base_record.is_exp:
            exception_msg = (
                f"{COLOR_WHITE_255} {'RAISE-EXCEPTION'.ljust(left_item_offset)}{COLOR_END}"
                f"{COLOR_ORANGE}{align_json_lines(left_item_offset + 1, full_record.exp_obj, True)}{COLOR_END}"
            )
        print(
            f"{COLOR_WHITE_255} {'INDEX'.ljust(left_item_offset)}{COLOR_END}{COLOR_ORANGE}{base_record.index}{COLOR_END}\n"
            f"{COLOR_WHITE_255} {'GMT-CREATE'.ljust(left_item_offset)}{COLOR_END}{COLOR_ORANGE}{time_ms_to_formatted_string(base_record.timestamp)}{COLOR_END}\n"
            f"{COLOR_WHITE_255} {'COST(ms)'.ljust(left_item_offset)}{COLOR_END}{COLOR_ORANGE}{cost_ms}{COLOR_END}\n"
            f"{COLOR_WHITE_255} {'MODULE'.ljust(left_item_offset)}{COLOR_END}{COLOR_ORANGE}{base_record.module_name}{COLOR_END}\n"
            f"{COLOR_WHITE_255} {'CLASS'.ljust(left_item_offset)}{COLOR_END}{COLOR_ORANGE}{base_record.class_name}{COLOR_END}\n"
            f"{COLOR_WHITE_255} {'METHOD'.ljust(left_item_offset)}{COLOR_END}{COLOR_ORANGE}{base_record.method_name}{COLOR_END}\n"
            f"{COLOR_WHITE_255} {'IS_RETURN'.ljust(left_item_offset)}{COLOR_END}{COLOR_ORANGE}{base_record.is_ret}{COLOR_END}\n"
            f"{COLOR_WHITE_255} {'IS_EXCEPTION'.ljust(left_item_offset)}{COLOR_END}{COLOR_ORANGE}{base_record.is_exp}{COLOR_END}\n"
            f"{COLOR_WHITE_255} {'ARGS'.ljust(left_item_offset)}{COLOR_END}{COLOR_ORANGE}{args_str}{COLOR_END}\n"
            f"{COLOR_WHITE_255} {'KWARGS'.ljust(left_item_offset)}{COLOR_END}{COLOR_ORANGE}{kwargs_str}{COLOR_END}\n"
            f"{return_obj}"
            f"{exception_msg}"
        )

    def render_tt_record(
        self, cli_base_record: BaseInvocationRecord, is_first: bool
    ) -> None:
        if is_first:
            self.__print_header()
        self.__print_base_record(cli_base_record)

    def render_records_list(self, list_records: bytes):
        list_records: List[BaseInvocationRecord] = pickle.loads(list_records)
        self.__print_header()
        for cli_base_record in list_records:
            self.__print_base_record(cli_base_record)

    def __print_header(self):
        terminal_width = shutil.get_terminal_size().columns
        print(
            f'{COLOR_BOLD}{COLOR_WHITE_255} {"INDEX":<9}{"TIMESTAMP":<25}{"COST(ms)":<10}{"IS-RET":<8}'
            f'{"IS-EXP":<8}{"MODULE":<30}METHOD{COLOR_END}'
        )
        print(f"{COLOR_FAINT}{BOX_HORIZONTAL * terminal_width}{COLOR_END}")

    def __print_base_record(self, record: BaseInvocationRecord):
        cost_ms: str = f"{record.cost_ms:.3f}"
        print(
            f" {str(record.index).ljust(9)}{time_ms_to_formatted_string(record.timestamp).ljust(25)}"
            f"{cost_ms.ljust(10)}{str(record.is_ret).ljust(8)}{str(record.is_exp).ljust(8)}"
            f"{record.module_name.ljust(max(len(record.module_name), 28) + 2)}{record.method_name}"
        )

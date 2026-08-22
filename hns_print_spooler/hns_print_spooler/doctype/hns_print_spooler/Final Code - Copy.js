frappe.query_reports["HNS Attendance - Dynarep - HIREN"] = {

    filters: [

        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
            reqd: 1
        },

        {
            fieldname: "filt_fdat",
            label: __("Filter From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(
                frappe.datetime.get_today(),
                -1
            )
        },

        {
            fieldname: "filt_tdat",
            label: __("Filter To Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(
                frappe.datetime.get_today(),
                -1
            )
        },

        {
            fieldname: "show_sunday",
            label: __("Show Sunday"),
            fieldtype: "Check",
            default: 0
        },

        {
            fieldname: "exclude_today",
            label: __("Exclude Today"),
            fieldtype: "Check",
            default: 0
        },

        {
            fieldname: "missed_punch",
            label: __("Missed Punch"),
            fieldtype: "Check",
            default: 0
        },

        {
            fieldname: "Status",
            label: __("Status"),
            fieldtype: "Select",
            options: ["", "Active", "Inactive"],
            default: "Active"
        },

        {
            fieldname: "employment_type",
            label: __("Employment Type"),
            fieldtype: "Link",
            options: "Employment Type",
            default: ""
        },

        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "MultiSelectList",
            options: "Employee",

            get_data: function(txt) {
                return frappe.db.get_link_options(
                    "Employee",
                    txt,
                    {
                        status: "Active"
                    }
                );
            }
        },

        {
            fieldname: "filt_repo_choice",
            label: __("Select Report"),
            fieldtype: "Autocomplete",
            options: hns.report.get_report_choice_options(),
            default: "",
            reqd: 1
        }
    ],

    get_datatable_options: function(options) {

        return Object.assign(options, {
            checkboxColumn: true
        });
    },

    onload: function(report) {

        hns.report.report_choice(
            report,
            "filt_repo_choice"
        );

        report.page.add_inner_button(
            __("Print Selected"),
            function() {
                print_selected_dynamic_rows(report);
            }
        );
    },

    formatter: function(
        value,
        row,
        column,
        data,
        default_formatter
    ) {

        if (!data) {
            return hns.report.default_formatter(
                value,
                row,
                column,
                data,
                default_formatter
            );
        }

        let formatted =
            hns.report.default_formatter(
                value,
                row,
                column,
                data,
                default_formatter
            );

        let styles = [];

        if (
            data.__is_total_row === true
        ) {
            styles.push("font-weight:bold");
        }

        if (
            data.rep_group_field &&
            String(data.is_last_grp) !== "1"
        ) {
            styles.push("font-weight:bold");
        }

        if (
            data.formatter &&
            String(data.formatter).trim()
        ) {
            styles.push(
                "color:" +
                String(data.formatter).trim()
            );
        }
        
         /*
         * YOUR TIME CONDITIONS
         */

        function timeToSec(time) {
            if (!time) {
                return null;
            }

            let parts = String(time).split(":");

            return (
                (parseInt(parts[0] || 0) * 3600) +
                (parseInt(parts[1] || 0) * 60) +
                parseInt(parts[2] || 0)
            );
        }

        let first_in = timeToSec(data["3from_time"]);
        let last_out = timeToSec(data["4last_time"]);
        let shift_start = timeToSec(data["start_time"]);
        let shift_end = timeToSec(data["end_time"]);

        /*
         * Late arrival: first_in > shift_start
         */

        if (
            column.fieldname === "3from_time" &&
            first_in !== null &&
            shift_start !== null &&
            first_in > shift_start
        ) {
            styles.push("color:red");
            styles.push("font-weight:bold");
        }

        /*
         * Early exit: last_out < shift_end
         */

        if (
            column.fieldname === "4last_time" &&
            last_out !== null &&
            shift_end !== null &&
            last_out < shift_end
        ) {
            styles.push("color:red");
            styles.push("font-weight:bold");
        }

        /*
         * Apply all styles together.
         * This preserves the original formatter colors,
         * except the time warning will correctly show red.
         */

        if (!styles.length) {
            return formatted;
        }

        return (
            '<span style="' +
            styles.join(";") +
            '">' +
            formatted +
            "</span>"
        );
    }
};


/* =========================================================
   CACHE
========================================================= */

let _cache = {
    report_data: null,
    report_columns: null,
    group_columns: [],
    is_header_row: [],
    is_detail_row: [],
    is_total_row: [],
    detail_row_indexes: [],
    header_level_by_index: {},
    normalized_by_field: {},
    detail_index_by_field: {},
    total_columns: [],
    total_label_column: null
};


function clear_cache() {

    _cache = {
        report_data: null,
        report_columns: null,
        group_columns: [],
        is_header_row: [],
        is_detail_row: [],
        is_total_row: [],
        detail_row_indexes: [],
        header_level_by_index: {},
        normalized_by_field: {},
        detail_index_by_field: {},
        total_columns: [],
        total_label_column: null
    };
}


/* =========================================================
   BASIC HELPERS
========================================================= */

function normalize_value(value) {

    return value == null
        ? ""
        : String(value)
            .trim()
            .toLowerCase()
            .replace(/\s+/g, " ");
}


function get_row_label(row) {

    if (!row) {
        return "";
    }

    const fields = [
        row.employee_name,
        row.employee,
        row.name,
        row.label,
        row.title
    ];

    for (const value of fields) {

        if (
            value != null &&
            String(value).trim()
        ) {
            return normalize_value(value);
        }
    }

    return "";
}


function is_total_column(column) {

    if (!column) {
        return false;
    }

    return [
        "int",
        "integer",
        "float",
        "currency",
        "percent"
    ].includes(
        String(column.fieldtype || "").toLowerCase()
    );
}


function is_original_grand_total_row(row) {

    const label = get_row_label(row);

    return (
        label === "grand total" ||
        label === "grandtotal"
    );
}


function is_original_total_row(row) {

    if (!row) {
        return false;
    }

    if (row.__is_total_row === true) {
        return true;
    }

    return [
        "sub total",
        "subtotal",
        "grand total",
        "grandtotal",
        "total"
    ].includes(
        get_row_label(row)
    );
}


function is_original_header_row(row) {

    if (!row) {
        return false;
    }

    if (row.__print_selected_header === true) {
        return false;
    }

    if (row.__is_dynamic_header === true) {
        return true;
    }

    if (is_original_total_row(row)) {
        return false;
    }

    return (
        row.rep_group_field != null &&
        String(row.rep_group_field).trim() !== ""
    );
}


function get_numeric_value(value) {

    if (
        value == null ||
        value === ""
    ) {
        return 0;
    }

    if (typeof value === "number") {
        return isNaN(value) ? 0 : value;
    }

    const number = parseFloat(
        String(value)
            .replace(/,/g, "")
            .replace(/%/g, "")
            .trim()
    );

    return isNaN(number) ? 0 : number;
}


/* =========================================================
   CACHE BUILD
========================================================= */

function ensure_cache(
    report_data,
    report_columns
) {

    if (
        _cache.report_data === report_data &&
        _cache.report_columns === report_columns
    ) {
        return;
    }

    clear_cache();

    _cache.report_data = report_data;
    _cache.report_columns = report_columns;

    _cache.group_columns =
        (report_columns || [])
            .filter(function(column) {
                return (
                    column &&
                    column.ar_index != null &&
                    Number(column.ar_index) > 0
                );
            })
            .sort(function(a, b) {
                return (
                    Number(a.ar_index) -
                    Number(b.ar_index)
                );
            });

    _cache.total_columns =
        (report_columns || [])
            .filter(function(column) {
                return (
                    column &&
                    column.fieldname &&
                    is_total_column(column)
                );
            })
            .map(function(column) {
                return {
                    fieldname: column.fieldname,
                    fieldtype: String(
                        column.fieldtype || ""
                    ).toLowerCase()
                };
            });

    _cache.total_label_column =
        find_total_label_column(
            report_columns
        );

    const row_count =
        report_data
            ? report_data.length
            : 0;

    const headers =
        new Array(row_count).fill(false);

    const details =
        new Array(row_count).fill(false);

    const totals =
        new Array(row_count).fill(false);

    const detail_indexes = [];

    const normalized_by_field = {};
    const detail_index_by_field = {};

    _cache.group_columns.forEach(function(column) {

        normalized_by_field[
            column.fieldname
        ] = new Array(row_count).fill("");

        detail_index_by_field[
            column.fieldname
        ] = {};
    });

    for (let i = 0; i < row_count; i++) {

        const row = report_data[i];

        if (!row) {
            continue;
        }

        const total =
            is_original_total_row(row);

        const header =
            !total &&
            is_original_header_row(row);

        const detail =
            !total &&
            !header;

        totals[i] = total;
        headers[i] = header;
        details[i] = detail;

        if (!detail) {
            continue;
        }

        detail_indexes.push(i);

        _cache.group_columns.forEach(function(column) {

            const fieldname =
                column.fieldname;

            const value =
                normalize_value(
                    row[fieldname]
                );

            normalized_by_field[
                fieldname
            ][i] = value;

            if (!value) {
                return;
            }

            if (
                !detail_index_by_field[
                    fieldname
                ][value]
            ) {
                detail_index_by_field[
                    fieldname
                ][value] = [];
            }

            detail_index_by_field[
                fieldname
            ][value].push(i);
        });
    }

    _cache.is_header_row = headers;
    _cache.is_detail_row = details;
    _cache.is_total_row = totals;
    _cache.detail_row_indexes = detail_indexes;
    _cache.normalized_by_field =
        normalized_by_field;
    _cache.detail_index_by_field =
        detail_index_by_field;
}


/* =========================================================
   HEADER HELPERS
========================================================= */

function get_dynamic_header_value(index) {

    const row =
        _cache.report_data[index];

    if (!row) {
        return "";
    }

    if (
        row.rep_group_field &&
        row[row.rep_group_field] != null &&
        String(row[row.rep_group_field]).trim()
    ) {
        return row[row.rep_group_field];
    }

    for (const column of _cache.group_columns) {

        const value =
            row[column.fieldname];

        if (
            value != null &&
            String(value).trim()
        ) {
            return value;
        }
    }

    const ignored = new Set([
        "rep_group_field",
        "_group_level",
        "is_last_grp",
        "__is_dynamic_header",
        "__is_total_row",
        "__source_index",
        "__header_level",
        "__total_label",
        "__row_class",
        "__show_group_total",
        "show_group_total"
    ]);

    for (const fieldname of Object.keys(row)) {

        if (ignored.has(fieldname)) {
            continue;
        }

        const value = row[fieldname];

        if (
            value != null &&
            String(value).trim()
        ) {
            return value;
        }
    }

    return "";
}


function get_dynamic_header_level(index) {

    if (
        _cache.header_level_by_index[index] !== undefined
    ) {
        return _cache.header_level_by_index[index];
    }

    const row =
        _cache.report_data[index];

    if (!row) {
        return null;
    }

    if (
        row.indent != null &&
        row.indent !== ""
    ) {

        const level =
            Number(row.indent);

        if (
            Number.isInteger(level) &&
            level >= 0
        ) {
            _cache.header_level_by_index[index] =
                level;

            return level;
        }
    }

    if (
        row._group_level != null &&
        row._group_level !== ""
    ) {

        const level =
            Number(row._group_level);

        if (
            Number.isInteger(level) &&
            level >= 0
        ) {
            _cache.header_level_by_index[index] =
                level;

            return level;
        }
    }

    if (
        !_cache.group_columns.length ||
        !_cache.detail_row_indexes.length
    ) {
        return null;
    }

    const header_value =
        normalize_value(
            get_dynamic_header_value(index)
        );

    if (!header_value) {
        return null;
    }

    for (
        let level = 0;
        level < _cache.group_columns.length;
        level++
    ) {

        const fieldname =
            _cache.group_columns[level].fieldname;

        const matches =
            _cache.detail_index_by_field[
                fieldname
            ];

        if (
            matches &&
            matches[header_value] &&
            matches[header_value].length
        ) {

            _cache.header_level_by_index[index] =
                level;

            return level;
        }
    }

    if (
        _cache.detail_row_indexes.length > 5000
    ) {
        return null;
    }

    for (
        let level = 0;
        level < _cache.group_columns.length;
        level++
    ) {

        const fieldname =
            _cache.group_columns[level].fieldname;

        const values =
            _cache.normalized_by_field[
                fieldname
            ];

        if (!values) {
            continue;
        }

        for (
            const detail_index of _cache.detail_row_indexes
        ) {

            const value =
                values[detail_index];

            if (
                value &&
                (
                    value.includes(header_value) ||
                    header_value.includes(value)
                )
            ) {

                _cache.header_level_by_index[index] =
                    level;

                return level;
            }
        }
    }
    _cache.header_level_by_index[index] = 0;
    return 0;
}


/* =========================================================
   TOTAL COLUMN / LABEL
========================================================= */

function find_total_label_column(columns) {

    const visible =
        (columns || []).filter(function(column) {

            return (
                column &&
                column.fieldname &&
                column.hidden !== true &&
                String(column.hidden) !== "1"
            );
        });

    return (
        visible.find(function(column) {
            return !is_total_column(column);
        }) ||
        visible[0] ||
        (columns || []).find(function(column) {
            return column && column.fieldname;
        }) ||
        null
    );
}


function get_total_label_column() {

    if (_cache.total_label_column) {
        return _cache.total_label_column;
    }

    _cache.total_label_column =
        find_total_label_column(
            _cache.report_columns
        );

    return _cache.total_label_column;
}


/* =========================================================
   GROUP COLOR
========================================================= */

function get_group_formatter(header_index) {

    const header =
        _cache.report_data[header_index];

    if (!header) {
        return "";
    }

    if (
        header.formatter != null &&
        String(header.formatter).trim()
    ) {
        return String(
            header.formatter
        ).trim();
    }

    const header_level =
        get_dynamic_header_level(
            header_index
        );

    for (
        let i = header_index + 1;
        i < _cache.report_data.length;
        i++
    ) {

        const row =
            _cache.report_data[i];

        if (!row) {
            continue;
        }

        if (_cache.is_header_row[i]) {

            const next_level =
                get_dynamic_header_level(i);

            if (
                next_level != null &&
                header_level != null &&
                next_level <= header_level
            ) {
                break;
            }
        }

        if (
            is_original_total_row(row) &&
            row.formatter
        ) {
            return String(
                row.formatter
            ).trim();
        }
    }

    return "";
}


function get_grand_total_formatter() {

    for (
        const row of _cache.report_data
    ) {

        if (
            is_original_grand_total_row(row) &&
            row.formatter
        ) {
            return String(
                row.formatter
            ).trim();
        }
    }

    for (
        let i = 0;
        i < _cache.report_data.length;
        i++
    ) {

        if (
            _cache.is_header_row[i] &&
            get_group_formatter(i)
        ) {
            return get_group_formatter(i);
        }
    }

    return "";
}


/* =========================================================
   FIND ORIGINAL SUBTOTAL
========================================================= */

function get_original_subtotal_level(total_index) {

    const row =
        _cache.report_data[total_index];

    if (!row) {
        return null;
    }

    if (
        row.__subtotal_group_level != null &&
        row.__subtotal_group_level !== ""
    ) {

        const level =
            Number(
                row.__subtotal_group_level
            );

        if (Number.isInteger(level)) {
            return level;
        }
    }

    const formatter =
        row.formatter
            ? String(row.formatter)
                .trim()
                .toLowerCase()
            : "";

    if (formatter) {

        for (
            let i = total_index - 1;
            i >= 0;
            i--
        ) {

            if (!_cache.is_header_row[i]) {
                continue;
            }

            const header =
                _cache.report_data[i];

            const header_formatter =
                header.formatter
                    ? String(header.formatter)
                        .trim()
                        .toLowerCase()
                    : "";

            if (
                header_formatter &&
                header_formatter === formatter
            ) {
                return get_dynamic_header_level(i);
            }
        }
    }

    for (
        let i = total_index - 1;
        i >= 0;
        i--
    ) {

        if (_cache.is_header_row[i]) {
            return get_dynamic_header_level(i);
        }
    }

    return null;
}


function find_original_subtotal_for_header(
    header_index
) {

    const header =
        _cache.report_data[header_index];

    if (!header) {
        return null;
    }

    const header_level =
        get_dynamic_header_level(
            header_index
        );

    if (header_level == null) {
        return null;
    }

    /*
     * First preference:
     * Explicit subtotal group level.
     */
    for (
        let i = header_index + 1;
        i < _cache.report_data.length;
        i++
    ) {

        const row =
            _cache.report_data[i];

        if (!row) {
            continue;
        }

        /*
         * A new header at the same or higher parent
         * level means the current group has ended.
         */
        if (
            _cache.is_header_row[i]
        ) {

            const next_level =
                get_dynamic_header_level(i);

            if (
                next_level != null &&
                next_level <= header_level
            ) {
                break;
            }

            continue;
        }

        if (
            !is_original_total_row(row)
        ) {
            continue;
        }

        if (
            is_original_grand_total_row(row)
        ) {
            break;
        }

        /*
         * Exact explicit level match.
         */
        if (
            row.__subtotal_group_level != null &&
            row.__subtotal_group_level !== ""
        ) {

            const subtotal_level =
                Number(
                    row.__subtotal_group_level
                );

            if (
                Number.isInteger(subtotal_level) &&
                subtotal_level === header_level
            ) {
                return row;
            }
        }
    }


    /*
     * Second preference:
     * Match formatter/color.
     *
     * This keeps your existing RED / BLUE / GREEN
     * subtotal colors.
     */
    const header_formatter =
        header.formatter
            ? String(
                header.formatter
            )
                .trim()
                .toLowerCase()
            : "";

    if (header_formatter) {

        for (
            let i = header_index + 1;
            i < _cache.report_data.length;
            i++
        ) {

            const row =
                _cache.report_data[i];

            if (!row) {
                continue;
            }

            if (
                _cache.is_header_row[i]
            ) {

                const next_level =
                    get_dynamic_header_level(i);

                if (
                    next_level != null &&
                    next_level <= header_level
                ) {
                    break;
                }

                continue;
            }

            if (
                !is_original_total_row(row)
            ) {
                continue;
            }

            if (
                is_original_grand_total_row(row)
            ) {
                break;
            }

            const subtotal_formatter =
                row.formatter
                    ? String(
                        row.formatter
                    )
                        .trim()
                        .toLowerCase()
                    : "";

            if (
                subtotal_formatter &&
                subtotal_formatter === header_formatter
            ) {
                return row;
            }
        }
    }


    /*
     * Final fallback:
     * Find the first subtotal belonging to this
     * hierarchy level.
     */
    for (
        let i = header_index + 1;
        i < _cache.report_data.length;
        i++
    ) {

        const row =
            _cache.report_data[i];

        if (!row) {
            continue;
        }

        if (
            _cache.is_header_row[i]
        ) {

            const next_level =
                get_dynamic_header_level(i);

            if (
                next_level != null &&
                next_level <= header_level
            ) {
                break;
            }

            continue;
        }

        if (
            !is_original_total_row(row)
        ) {
            continue;
        }

        if (
            is_original_grand_total_row(row)
        ) {
            break;
        }

        return row;
    }

    return null;
}


/* =========================================================
   PRINT HELPERS
========================================================= */

function copy_dynamic_header(row, header_index) {

    const copy = {};

    /*
     * -------------------------------------------------
     * ONLY PUT HEADER TEXT IN THE LABEL COLUMN
     * -------------------------------------------------
     */

    const label_column =
        get_total_label_column();

    if (
        label_column &&
        label_column.fieldname
    ) {

        copy[label_column.fieldname] =
            get_dynamic_header_value(
                header_index
            );
    }

    /*
     * -------------------------------------------------
     * KEEP HEADER COLOR
     * -------------------------------------------------
     */

    if (
        row.formatter != null &&
        String(row.formatter).trim()
    ) {

        copy.formatter =
            String(row.formatter).trim();
    }

    /*
     * -------------------------------------------------
     * HEADER FLAGS
     * -------------------------------------------------
     */

    copy.__print_selected_header = true;

    copy.__is_dynamic_header = true;

    copy.__row_class =
        "dynamic-report-header";

    return copy;
}


function create_total_row(
    label,
    indexes,
    formatter,
    is_subtotal = false
) {

    const row = {};

    const label_column =
        get_total_label_column();

    if (
        label_column &&
        label_column.fieldname
    ) {
        row[label_column.fieldname] =
            label;
    }

    const total_columns =
        _cache.total_columns;

    for (const column of total_columns) {

        /*
         * -------------------------------------------------
         * SUB TOTAL
         *
         * Keep Minutes blank.
         * -------------------------------------------------
         */
        if (
            is_subtotal &&
            (
                String(column.fieldname || "")
                    .trim()
                    .toLowerCase() === "minutes"
            )
        ) {
            row[column.fieldname] = "";
            continue;
        }

        let total = 0;

        for (const index of indexes) {

            const source =
                _cache.report_data[index];

            if (!source) {
                continue;
            }

            total +=
                get_numeric_value(
                    source[column.fieldname]
                );
        }

        row[column.fieldname] =
            (
                column.fieldtype === "int" ||
                column.fieldtype === "integer"
            )
                ? Math.round(total)
                : Number(total.toFixed(2));
    }

    if (formatter) {
        row.formatter = formatter;
    }

    row.__is_total_row = true;

    row.__total_label =
        label;

    row.__row_class =
        "total-report-row";

    return row;
}


/* =========================================================
   PRINT SELECTED
========================================================= */

function print_selected_dynamic_rows(report) {

    const datatable =
        report.datatable;

    if (
        !datatable ||
        !datatable.rowmanager ||
        !datatable.rowmanager.getCheckedRows
    ) {

        frappe.msgprint(
            __("Unable to read selected rows.")
        );

        return;
    }

    const checked_rows =
        datatable.rowmanager.getCheckedRows();

    const report_data =
        report.data || [];

    const report_columns =
        report.columns || [];

    ensure_cache(
        report_data,
        report_columns
    );

    const selected_indexes = [];

    for (const checked of checked_rows) {

        const index =
            Number(checked);

        if (
            !Number.isInteger(index) ||
            index < 0 ||
            index >= report_data.length
        ) {
            continue;
        }

        if (
            !_cache.is_detail_row[index]
        ) {
            continue;
        }

        selected_indexes.push(index);
    }

    const unique_selected =
        [...new Set(selected_indexes)]
            .sort(function(a, b) {
                return a - b;
            });

    if (!unique_selected.length) {

        frappe.msgprint(
            __("Please select at least one detail row.")
        );

        return;
    }

    const original_get_data =
        report.get_data_for_print;

    let has_column_filter = false;
    try {
        if (report && report.wrapper) {
            $(report.wrapper).find('.dt-header .dt-filter, .dt-header input.dt-filter').each(function() {
                let val = $(this).val();
                if (val && String(val).trim() !== '') {
                    has_column_filter = true;
                }
            });
        }
    } catch(e) {
        console.error("Error checking filters", e);
    }

    report.get_data_for_print =
        function() {

            return build_selected_print_data(
                report_data,
                report_columns,
                unique_selected,
                has_column_filter
            );
        };

    frappe.ui.get_print_settings(
        false,

        function(print_settings) {

            print_settings.custom_css = `
                .print-format table th:first-child,
                .print-format table td:first-child {
                    display: none !important;
                }

                .print-format tr.dynamic-report-header {
                    display: table-row !important;
                }

                .print-format tr.dynamic-report-header td {
                    font-weight: bold !important;
                    border-top: 1px solid #888 !important;
                    border-bottom: 1px solid #888 !important;
                }

                .print-format tr.total-report-row td {
                    font-weight: bold !important;
                    border-top: 1px solid #555 !important;
                }
            `;

            Promise
                .resolve(
                    report.print_report(
                        print_settings
                    )
                )
                .finally(function() {

                    report.get_data_for_print =
                        original_get_data;
                
                    setTimeout(function() {
                
                        if (report.datatable &&
                            report.datatable.rowmanager) {
                
                            // Clear selected rows
                            report.datatable.rowmanager.checkedRows = [];
                
                            // Refresh table UI
                            report.datatable.refresh(
                                report.data,
                                report.columns
                            );
                        }
                
                    }, 300);
                });
        },

        null,
        report.columns,
        true
    );
}

function build_selected_print_data(
    report_data,
    report_columns,
    selected_indexes,
    has_column_filter
) {

    ensure_cache(
        report_data,
        report_columns
    );

    const selected_set =
        new Set(selected_indexes);

    const print_rows = [];

    if (has_column_filter) {
        for (const index of selected_indexes) {
            if (!_cache.is_detail_row[index]) continue;
            const row = report_data[index];
            if (!row) continue;
            
            const copy = Object.assign({}, row);
            delete copy.__is_dynamic_header;
            delete copy.__is_total_row;
            delete copy.__total_label;
            delete copy.__row_class;
            delete copy.__print_selected_header;
            
            print_rows.push(copy);
        }
        return print_rows;
    }

    /*
     * =====================================================
     * STEP 1
     * Find the header hierarchy for every selected detail.
     *
     * IMPORTANT:
     * TOTAL / SUB TOTAL rows are completely ignored while
     * walking backwards.
     *
     * This allows:
     *
     * GREEN
     *   BLUE 1
     *     RED
     *       Detail
     *     RED TOTAL
     *   BLUE TOTAL
     *
     *   BLUE 2
     *     RED
     *       Detail
     *
     * to correctly become:
     *
     * GREEN -> BLUE 2 -> RED
     * =====================================================
     */

    const header_chains = new Map();

    for (const detail_index of selected_indexes) {

        if (
            !_cache.is_detail_row[detail_index]
        ) {
            continue;
        }

        const headers_by_level = {};

        for (
            let i = detail_index - 1;
            i >= 0;
            i--
        ) {

            const row =
                report_data[i];

            if (!row) {
                continue;
            }


            /*
             * Ignore ALL subtotal / total rows.
             *
             * This is the important part.
             */
            if (
                _cache.is_total_row[i]
            ) {
                continue;
            }


            /*
             * Ignore normal detail rows.
             */
            if (
                !_cache.is_header_row[i]
            ) {
                continue;
            }


            let level =
                get_dynamic_header_level(i);


            /*
             * If _group_level exists, ALWAYS prefer it.
             */
            if (
                row._group_level != null &&
                row._group_level !== ""
            ) {

                const explicit_level =
                    Number(row._group_level);

                if (
                    Number.isInteger(
                        explicit_level
                    ) &&
                    explicit_level >= 0
                ) {
                    level =
                        explicit_level;
                }
            }


            if (
                level == null ||
                !Number.isInteger(level)
            ) {
                continue;
            }


            /*
             * We are walking backwards.
             *
             * Therefore the FIRST header found for a
             * particular level is the nearest/current one.
             *
             * Example:
             *
             * GREEN = level 0
             * BLUE  = level 1
             * RED   = level 2
             */
            if (
                headers_by_level[level] === undefined
            ) {

                headers_by_level[level] = {
                    index: i,
                    level: level
                };
            }


            /*
             * Once level 0 is found, hierarchy is complete.
             */
            if (level === 0) {
                break;
            }
        }


        const headers =
            Object.keys(headers_by_level)
                .map(function(level) {

                    return headers_by_level[level];

                })
                .sort(function(a, b) {

                    return (
                        a.level -
                        b.level
                    );

                });


        header_chains.set(
            detail_index,
            headers
        );
    }


    /*
     * =====================================================
     * STEP 2
     * Build tree.
     *
     * IMPORTANT:
     * Header index is used as the unique key.
     *
     * Therefore:
     *
     * BLUE #1
     * BLUE #2
     *
     * are TWO different groups even if their names are
     * exactly the same.
     * =====================================================
     */

    function create_node(
        parent,
        header
    ) {

        const key =
            String(header.index);

        if (
            !parent.children.has(key)
        ) {

            parent.children.set(
                key,
                {
                    header: header,
                    children: new Map(),
                    details: []
                }
            );
        }

        return parent.children.get(key);
    }


    const root = {
        children: new Map(),
        details: []
    };


    for (const detail_index of selected_indexes) {

        if (
            !_cache.is_detail_row[detail_index]
        ) {
            continue;
        }

        const headers =
            header_chains.get(
                detail_index
            ) || [];


        let current =
            root;


        for (const header of headers) {

            current =
                create_node(
                    current,
                    header
                );
        }


        current.details.push(
            detail_index
        );
    }


    /*
     * =====================================================
     * STEP 3
     * Check whether node contains selected details.
     * =====================================================
     */

    function has_selected_details(node) {

        if (!node) {
            return false;
        }


        for (
            const index of node.details || []
        ) {

            if (
                selected_set.has(index)
            ) {
                return true;
            }
        }


        for (
            const child of
            node.children.values()
        ) {

            if (
                has_selected_details(child)
            ) {
                return true;
            }
        }


        return false;
    }


    /*
     * =====================================================
     * STEP 4
     * Collect only selected details.
     * =====================================================
     */

    function collect_selected_details(node) {

        const result = [];


        for (
            const index of
            node.details || []
        ) {

            if (
                selected_set.has(index)
            ) {
                result.push(index);
            }
        }


        for (
            const child of
            node.children.values()
        ) {

            result.push(
                ...collect_selected_details(
                    child
                )
            );
        }


        return [
            ...new Set(result)
        ].sort(function(a, b) {

            return a - b;

        });
    }


    /*
     * =====================================================
     * STEP 5
     * Render hierarchy.
     *
     * ORDER:
     *
     * GREEN
     *   BLUE
     *     RED
     *       Detail
     *     RED Sub Total
     *   BLUE Sub Total
     *
     *   BLUE
     *     RED
     *       Detail
     *     RED Sub Total
     *   BLUE Sub Total
     *
     * GREEN Sub Total
     * =====================================================
     */

    function render_group(node) {

        if (
            !node ||
            !node.header
        ) {
            return;
        }


        const header_index =
            node.header.index;


        const header_row =
            report_data[header_index];


        if (!header_row) {
            return;
        }


        /*
         * -------------------------------------------------
         * 1. PRINT HEADER
         * -------------------------------------------------
         */

        print_rows.push(
            copy_dynamic_header(
                header_row,
                header_index
            )
        );


        /*
         * -------------------------------------------------
         * 2. PRINT CHILD GROUPS
         * -------------------------------------------------
         *
         * This is what creates:
         *
         * GREEN
         *   BLUE
         *     RED
         */

        node.children.forEach(
            function(child) {

                if (
                    has_selected_details(child)
                ) {

                    render_group(
                        child
                    );
                }
            }
        );


        /*
         * -------------------------------------------------
         * 3. PRINT DETAILS THAT BELONG DIRECTLY TO THIS
         *    GROUP
         * -------------------------------------------------
         */

        const own_details =
            (node.details || [])
                .filter(function(index) {

                    return selected_set.has(
                        index
                    );

                })
                .sort(function(a, b) {

                    return a - b;

                });


        for (
            const detail_index of own_details
        ) {

            const row =
                report_data[
                    detail_index
                ];


            if (!row) {
                continue;
            }


            const copy =
                Object.assign(
                    {},
                    row
                );


            delete copy.__is_dynamic_header;
            delete copy.__is_total_row;
            delete copy.__total_label;
            delete copy.__row_class;
            delete copy.__print_selected_header;


            print_rows.push(
                copy
            );
        }


        /*
         * -------------------------------------------------
         * 4. FIND SELECTED DETAILS UNDER THIS GROUP
         * -------------------------------------------------
         */

        const group_details =
            collect_selected_details(
                node
            );


        if (
            !group_details.length
        ) {
            return;
        }


        /*
         * -------------------------------------------------
         * 5. FIND ORIGINAL SUBTOTAL ONLY FOR:
         *
         *    - COLOR / FORMATTER
         *    - GROUP LEVEL
         *
         * NEVER copy its numeric values.
         * -------------------------------------------------
         */

        const original_subtotal =
            find_original_subtotal_for_header(
                header_index
            );


        /*
         * If original subtotal is not found,
         * still create our own subtotal.
         */

        let subtotal_formatter = "";


        if (
            original_subtotal &&
            original_subtotal.formatter
        ) {

            subtotal_formatter =
                String(
                    original_subtotal.formatter
                ).trim();

        }


        if (!subtotal_formatter) {

            subtotal_formatter =
                get_group_formatter(
                    header_index
                );

        }


        /*
         * -------------------------------------------------
         * 6. RECALCULATE SUBTOTAL
         *
         * THIS IS THE IMPORTANT FIX.
         *
         * We DO NOT do:
         *
         * Object.assign({}, original_subtotal)
         *
         * because that copies old values like 96485.
         * -------------------------------------------------
         */

        const subtotal =
            create_total_row(
                __("Sub Total"),
                group_details,
                subtotal_formatter,
                true
            );


        /*
         * Keep original color.
         */

        if (
            subtotal_formatter
        ) {

            subtotal.formatter =
                subtotal_formatter;
        }


        /*
         * Metadata
         */

        subtotal.__is_total_row =
            true;

        subtotal.__total_label =
            __("Sub Total");

        subtotal.__row_class =
            "total-report-row";

        subtotal.__subtotal_group_level =
            node.header.level;

        subtotal.__subtotal_header_index =
            header_index;

        subtotal.__is_selected_subtotal =
            true;


        /*
         * -------------------------------------------------
         * 7. PRINT SUBTOTAL
         * -------------------------------------------------
         */

        print_rows.push(
            subtotal
        );
    }


    /*
     * =====================================================
     * STEP 6
     * Render top-level groups.
     *
     * This should normally be GREEN.
     * =====================================================
     */

    root.children.forEach(
        function(node) {

            if (
                has_selected_details(node)
            ) {

                render_group(node);
            }
        }
    );


    /*
     * =====================================================
     * STEP 7
     * Details without ANY group.
     * =====================================================
     */

    for (
        const index of root.details
    ) {

        if (
            !selected_set.has(index)
        ) {
            continue;
        }


        const row =
            report_data[index];


        if (!row) {
            continue;
        }


        print_rows.push(
            Object.assign(
                {},
                row
            )
        );
    }


    /*
     * =====================================================
     * STEP 8
     * GRAND TOTAL
     *
     * Only selected detail rows are included.
     * =====================================================
     */

    const grand_total =
        create_total_row(
            __("Grand Total"),
            selected_indexes,
            get_grand_total_formatter()
        );


    grand_total.__is_grand_total =
        true;


    print_rows.push(
        grand_total
    );


    /*
     * =====================================================
     * STEP 9
     * Remove original report headers/totals.
     *
     * Keep ONLY:
     *
     * - our dynamic headers
     * - our recalculated subtotals
     * - selected detail rows
     * - our grand total
     * =====================================================
     */

    return print_rows.filter(
        function(row) {

            if (!row) {
                return false;
            }


            /*
             * Our generated header
             */
            if (
                row.__print_selected_header === true
            ) {
                return true;
            }


            /*
             * Our generated subtotal / grand total
             */
            if (
                row.__is_total_row === true
            ) {
                return true;
            }


            /*
             * Never print original headers.
             */
            if (
                is_original_header_row(row)
            ) {
                return false;
            }


            /*
             * Never print original subtotals.
             */
            if (
                is_original_total_row(row)
            ) {
                return false;
            }


            /*
             * Only selected detail rows.
             */
            const index =
                report_data.indexOf(row);


            if (
                index !== -1 &&
                !selected_set.has(index)
            ) {
                return false;
            }


            return true;
        }
    );
}
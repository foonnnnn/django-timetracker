/*global $,window*/

function applyClass(What) {
	"use strict";
    // "overloaded" due to sharing code.
}

function change_table_data() {
	"use strict";
    var year = $("#year_select").val(),
        month = $("#month_select").val();
    window.location.href = [
        '/team_planning/',
        year, '/',
        month, '/'
    ].join('');
}

function addFunctions() {
	"use strict";
    $("#year_select").val($("#holiday-table").attr("year"));
    $("#month_select").val($("#holiday-table").attr("month"));
    $("#process_select").val($("#holiday-table").attr("process"));

    $("#year_select, #month_select, #process_select").change(function () {
        change_table_data();
    });

    $("#holiday-table")
        .attr("border", "1");
}

$(function () {
    "use strict";
    addFunctions();
});

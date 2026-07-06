frappe.pages['ai-education-dashboard'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'AI Education Suite',
		single_column: true,
	});

	page.set_secondary_action('Refresh', () => render_dashboard(page), 'refresh');

	render_dashboard(page);
};

function render_dashboard(page) {
	const $body = $(page.body);
	$body.empty();
	inject_ai_edu_styles();
	$body.append(ai_edu_dashboard_html());
	ai_edu_load_kpis($body);
	ai_edu_load_insight($body, false);

	$body.on('click', '.ai-edu-kpi-card', function () {
		const key = $(this).data('key');
		const label = $(this).data('label');
		if (key === 'question_paper_drafts') {
			ai_edu_show_question_paper_list();
		} else {
			ai_edu_show_kpi_dialog(key, label);
		}
	});

	$body.on('click', '#ai-edu-regenerate', function () {
		ai_edu_load_insight($body, true);
	});

	$body.on('click', '#ai-edu-grade-images-btn', function () {
		ai_edu_show_grade_images_dialog();
	});

	$body.on('click', '#ai-edu-generate-paper-btn', function () {
		ai_edu_show_generate_paper_dialog();
	});

	$body.on('click', '#ai-edu-manage-houses-btn', function () {
		ai_edu_show_manage_houses_dialog();
	});

	$body.on('click', '.ai-edu-more-link', function () {
		const doctype = $(this).data('doctype');
		const view = $(this).data('view');
		if (view === 'form') {
			frappe.set_route('Form', doctype, $(this).data('name') || doctype);
		} else {
			frappe.set_route('List', doctype);
		}
	});

	$body.on('click', '#ai-edu-chat-send', function () {
		ai_edu_send_chat_query($body);
	});
	$body.on('keydown', '#ai-edu-chat-input', function (e) {
		if (e.key === 'Enter') {
			ai_edu_send_chat_query($body);
		}
	});
}

function ai_edu_dashboard_html() {
	return `
	<div class="ai-edu-dashboard">
		<div class="ai-edu-header">
			<div>
				<div class="ai-edu-title">AI Education Suite</div>
				<div class="ai-edu-subtitle">Live overview of AI-generated suggestions</div>
			</div>
			<div class="ai-edu-status"><span class="ai-edu-dot"></span> Live</div>
		</div>
		<div class="ai-edu-actions-row">
			<button class="btn ai-edu-action-btn" id="ai-edu-grade-images-btn">
				✍ Grade Answer Sheet with AI
			</button>
			<button class="btn ai-edu-action-btn" id="ai-edu-generate-paper-btn">
				📄 Generate Question Paper from Material
			</button>
			<button class="btn ai-edu-action-btn" id="ai-edu-manage-houses-btn">
				⌂ Manage Houses
			</button>
		</div>
		<div class="ai-edu-kpi-row" id="ai-edu-kpi-row">
			<div class="ai-edu-loading">Loading KPIs…</div>
		</div>
		<div class="ai-edu-chat-card">
			<div class="ai-edu-chat-header">💬 Ask the Query Assistant</div>
			<div class="ai-edu-chat-messages" id="ai-edu-chat-messages">
				<div class="ai-edu-chat-msg ai-edu-chat-msg-ai">Ask me things like "how many students scored below 60% in Physics?"</div>
			</div>
			<div class="ai-edu-chat-input-row">
				<input type="text" id="ai-edu-chat-input" class="form-control" placeholder="Type a question…" />
				<button class="btn btn-primary" id="ai-edu-chat-send">Send</button>
			</div>
		</div>
		<div class="ai-edu-insight-card">
			<div class="ai-edu-insight-header">
				<span>★ AI INSIGHT</span>
				<button class="btn btn-xs ai-edu-btn" id="ai-edu-regenerate">Regenerate with AI</button>
			</div>
			<div class="ai-edu-insight-text" id="ai-edu-insight-text">Loading…</div>
		</div>
		<div class="ai-edu-more-section">
			<div class="ai-edu-more-header">More</div>
			<div class="ai-edu-more-row">
				<div class="ai-edu-more-link" data-view="list" data-doctype="Class Performance Snapshot">Class Performance Snapshot</div>
				<div class="ai-edu-more-link" data-view="list" data-doctype="Topic Tag">Topic Tag</div>
				<div class="ai-edu-more-link" data-view="list" data-doctype="Team Balance Suggestion">Team Balance Suggestion</div>
				<div class="ai-edu-more-link" data-view="list" data-doctype="House">House</div>
				<div class="ai-edu-more-link" data-view="list" data-doctype="Query Assistant Log">Query Assistant Log</div>
				<div class="ai-edu-more-link" data-view="form" data-doctype="AI Settings" data-name="AI Settings">AI Settings</div>
			</div>
		</div>
	</div>
	`;
}

function ai_edu_load_kpis($body) {
	frappe.call({
		method: 'ai_education_suite.ai_core.api.dashboard.get_kpis',
		callback: function (r) {
			if (!r.message) return;
			const $row = $body.find('#ai-edu-kpi-row');
			$row.empty();
			r.message.forEach(function (k) {
				$row.append(`
					<div class="ai-edu-kpi-card" data-key="${k.key}" data-label="${frappe.utils.escape_html(k.label)}" style="--kpi-color:${k.color}">
						<div class="ai-edu-kpi-icon">${k.icon}</div>
						<div class="ai-edu-kpi-value">${k.value}</div>
						<div class="ai-edu-kpi-label">${frappe.utils.escape_html(k.label)}</div>
					</div>
				`);
			});
		},
	});
}

function ai_edu_load_insight($body, use_llm) {
	const method = use_llm
		? 'ai_education_suite.ai_core.api.dashboard.get_ai_insight_llm'
		: 'ai_education_suite.ai_core.api.dashboard.get_ai_insight';
	$body.find('#ai-edu-insight-text').text(use_llm ? 'Asking the model…' : 'Loading…');
	frappe.call({
		method: method,
		callback: function (r) {
			$body.find('#ai-edu-insight-text').text(r.message || 'No insight available.');
		},
		error: function () {
			$body.find('#ai-edu-insight-text').text('Could not generate an AI insight right now.');
		},
	});
}

function ai_edu_show_kpi_dialog(key, label) {
	frappe.call({
		method: 'ai_education_suite.ai_core.api.dashboard.get_kpi_records',
		args: { key: key },
		callback: function (r) {
			if (!r.message) return;
			const doctype = r.message.doctype;
			const rows = r.message.rows;
			const dialog = new frappe.ui.Dialog({
				title: label,
				size: 'large',
				fields: [{ fieldtype: 'HTML', fieldname: 'list_html' }],
			});
			if (!rows.length) {
				dialog.fields_dict.list_html.$wrapper.html('<p class="text-muted">Nothing here right now.</p>');
			} else {
				const html = rows
					.map(function (row) {
						const title = row.student || row.title || row.applicant_name || row.name;
						return `
							<div class="ai-edu-list-row" data-doctype="${doctype}" data-name="${row.name}">
								<div>
									<div class="ai-edu-list-title">${frappe.utils.escape_html(title)}</div>
									<div class="ai-edu-list-sub">${frappe.utils.escape_html(row.name)}</div>
								</div>
								<button class="btn btn-xs btn-default ai-edu-open-btn">Open →</button>
							</div>
						`;
					})
					.join('');
				dialog.fields_dict.list_html.$wrapper.html(`<div class="ai-edu-list">${html}</div>`);
				dialog.fields_dict.list_html.$wrapper.on('click', '.ai-edu-open-btn, .ai-edu-list-row', function () {
					const $row = $(this).closest('.ai-edu-list-row');
					frappe.set_route('Form', $row.data('doctype'), $row.data('name'));
					dialog.hide();
				});
			}
			dialog.show();
		},
	});
}

function ai_edu_show_question_paper_list() {
	frappe.call({
		method: 'ai_education_suite.ai_core.api.dashboard.get_kpi_records',
		args: { key: 'question_paper_drafts' },
		callback: function (r) {
			if (!r.message) return;
			const rows = r.message.rows;
			const dialog = new frappe.ui.Dialog({
				title: 'Question Paper Drafts',
				size: 'large',
				fields: [{ fieldtype: 'HTML', fieldname: 'list_html' }],
			});
			const html =
				rows
					.map(function (row) {
						return `
							<div class="ai-edu-list-row" data-name="${row.name}">
								<div>
									<div class="ai-edu-list-title">${frappe.utils.escape_html(row.title || row.name)}</div>
									<div class="ai-edu-list-sub">${frappe.utils.escape_html(row.course || '')} · ${row.total_marks || 0} marks · ${row.status}</div>
								</div>
								<div>
									<button class="btn btn-xs btn-default ai-edu-preview-btn">Preview</button>
									<button class="btn btn-xs btn-default ai-edu-open-btn">Open →</button>
								</div>
							</div>
						`;
					})
					.join('') || '<p class="text-muted">No drafts yet.</p>';
			dialog.fields_dict.list_html.$wrapper.html(`<div class="ai-edu-list">${html}</div>`);
			dialog.fields_dict.list_html.$wrapper.on('click', '.ai-edu-open-btn', function () {
				const name = $(this).closest('.ai-edu-list-row').data('name');
				frappe.set_route('Form', 'AI Question Paper Draft', name);
				dialog.hide();
			});
			dialog.fields_dict.list_html.$wrapper.on('click', '.ai-edu-preview-btn', function () {
				const name = $(this).closest('.ai-edu-list-row').data('name');
				dialog.hide();
				ai_edu_show_question_paper_preview(name);
			});
			dialog.show();
		},
	});
}

function ai_edu_show_question_paper_preview(name) {
	frappe.call({
		method: 'ai_education_suite.ai_core.api.dashboard.get_question_paper_preview',
		args: { name: name },
		callback: function (r) {
			if (!r.message) return;
			const data = r.message;
			const dialog = new frappe.ui.Dialog({
				title: data.title || 'Question Paper Preview',
				size: 'large',
				fields: [{ fieldtype: 'HTML', fieldname: 'preview_html' }],
				primary_action_label: 'Download .docx',
				primary_action: function () {
					window.open(
						`/api/method/ai_education_suite.ai_core.api.dashboard.download_question_paper_docx?name=${encodeURIComponent(name)}`
					);
				},
			});
			const questions_html = data.questions
				.map(function (q, i) {
					return `
						<p class="ai-edu-doc-q"><b>${i + 1}.</b> ${frappe.utils.escape_html(q.question_text)}
						<br><span class="ai-edu-doc-meta">[${frappe.utils.escape_html(q.topic || '')} — ${frappe.utils.escape_html(q.difficulty || '')} — ${q.marks || 0} marks]</span></p>
					`;
				})
				.join('');
			const meta_line = [data.course, data.student_group, data.total_marks ? data.total_marks + ' marks' : '']
				.filter(Boolean)
				.join(' · ');
			dialog.fields_dict.preview_html.$wrapper.html(`
				<div class="ai-edu-doc-page">
					<div class="ai-edu-doc-title">${frappe.utils.escape_html(data.title || '')}</div>
					<div class="ai-edu-doc-meta-line">${frappe.utils.escape_html(meta_line)}</div>
					<hr>
					${questions_html}
				</div>
			`);
			dialog.show();
		},
	});
}

function ai_edu_show_grade_images_dialog() {
	const step1 = new frappe.ui.Dialog({
		title: 'Grade Answer Sheets — Step 1: Subject & Class',
		size: 'small',
		fields: [
			{ fieldtype: 'Link', fieldname: 'course', label: 'Subject / Course', options: 'Course', reqd: 1 },
			{ fieldtype: 'Link', fieldname: 'student_group', label: 'Class / Section', options: 'Student Group', reqd: 1 },
		],
		primary_action_label: 'Continue',
		primary_action: function (values) {
			step1.hide();
			ai_edu_show_grading_step2(values.course, values.student_group);
		},
	});
	step1.show();
}

function ai_edu_show_grading_step2(course, student_group) {
	frappe.call({
		method: 'ai_education_suite.ai_core.api.grading_workflow.get_students_for_course_and_group',
		args: { course: course, student_group: student_group },
		freeze: true,
		callback: function (r1) {
			if (!r1.message) return;
			const enrollment_tracked = r1.message.enrollment_tracked;
			const students = r1.message.students || [];
			frappe.call({
				method: 'ai_education_suite.ai_core.api.grading_workflow.get_question_paper_upload',
				args: { course: course, student_group: student_group },
				callback: function (r2) {
					ai_edu_render_grading_step2_dialog(course, student_group, students, enrollment_tracked, r2.message);
				},
			});
		},
	});
}

function ai_edu_render_grading_step2_dialog(course, student_group, students, enrollment_tracked, existing_paper) {
	const dialog = new frappe.ui.Dialog({
		title: `Grade Answer Sheets — ${course} / ${student_group}`,
		size: 'large',
		fields: [
			{ fieldtype: 'HTML', fieldname: 'paper_html' },
			{ fieldtype: 'Attach', fieldname: 'new_paper_image', label: 'Upload Question Paper (photo, once)' },
			{ fieldtype: 'HTML', fieldname: 'students_html' },
		],
	});

	let current_paper = existing_paper;

	function render_paper_section(paper) {
		if (paper) {
			const when = paper.uploaded_on ? frappe.datetime.str_to_user(paper.uploaded_on) : 'just now';
			dialog.fields_dict.paper_html.$wrapper.html(`
				<div class="ai-edu-paper-status">
					✓ Question paper already on file for this subject/class (uploaded ${when}).
					<button class="btn btn-xs btn-default" id="ai-edu-replace-paper-btn">Replace</button>
				</div>
			`);
			dialog.set_df_property('new_paper_image', 'hidden', 1);
		} else {
			dialog.fields_dict.paper_html.$wrapper.html(`
				<div class="ai-edu-paper-status">
					No question paper uploaded yet for this subject/class — upload it once below,
					it'll then be reused for every student.
				</div>
			`);
			dialog.set_df_property('new_paper_image', 'hidden', 0);
		}
	}
	render_paper_section(current_paper);

	dialog.fields_dict.paper_html.$wrapper.on('click', '#ai-edu-replace-paper-btn', function () {
		current_paper = null;
		render_paper_section(null);
	});

	function render_students() {
		const html =
			students
				.map(function (s) {
					const enroll_btn =
						enrollment_tracked && !s.enrolled
							? `<button class="btn btn-xs btn-default ai-edu-enroll-btn" data-student="${s.student}">+ Enroll in this subject</button>`
							: '';
					const can_grade = s.enrolled || !enrollment_tracked;
					const grade_btn = can_grade
						? `<button class="btn btn-xs btn-primary ai-edu-grade-student-btn" data-student="${s.student}" data-name="${frappe.utils.escape_html(s.student_name)}">Upload Answer Sheet & Grade</button>`
						: '';
					return `
						<div class="ai-edu-list-row" data-student="${s.student}">
							<div>
								<div class="ai-edu-list-title">${frappe.utils.escape_html(s.student_name)}</div>
								<div class="ai-edu-list-sub">${enrollment_tracked ? (s.enrolled ? 'Enrolled' : 'Not enrolled in this subject') : ''}</div>
							</div>
							<div>${enroll_btn} ${grade_btn}</div>
						</div>
					`;
				})
				.join('') || '<p class="text-muted">No students found in this class/section.</p>';
		dialog.fields_dict.students_html.$wrapper.html(`<div class="ai-edu-list">${html}</div>`);
	}
	render_students();

	dialog.fields_dict.students_html.$wrapper.on('click', '.ai-edu-enroll-btn', function () {
		const student = $(this).data('student');
		frappe.call({
			method: 'ai_education_suite.ai_core.api.grading_workflow.enroll_student_in_course',
			args: { student: student, course: course },
			freeze: true,
			callback: function () {
				frappe.show_alert({ message: 'Enrolled.', indicator: 'green' });
				dialog.hide();
				ai_edu_show_grading_step2(course, student_group);
			},
		});
	});

	dialog.fields_dict.students_html.$wrapper.on('click', '.ai-edu-grade-student-btn', function () {
		const student = $(this).data('student');
		const student_name = $(this).data('name');

		function do_grade(paper_ref) {
			ai_edu_show_answer_sheet_dialog(student, student_name, course, paper_ref);
		}

		if (current_paper) {
			do_grade({ question_paper_upload: current_paper.name });
		} else {
			const new_image = dialog.get_value('new_paper_image');
			if (!new_image) {
				frappe.show_alert({ message: 'Upload the question paper photo first (once, above).', indicator: 'red' });
				return;
			}
			frappe.call({
				method: 'ai_education_suite.ai_core.api.grading_workflow.save_question_paper_upload',
				args: { course: course, student_group: student_group, file_url: new_image },
				freeze: true,
				callback: function (r) {
					current_paper = { name: r.message.name };
					render_paper_section({ uploaded_on: null });
					do_grade({ question_paper_upload: r.message.name });
				},
			});
		}
	});

	dialog.show();
}

function ai_edu_show_answer_sheet_dialog(student, student_name, course, paper_ref) {
	const dialog = new frappe.ui.Dialog({
		title: `Answer Sheet — ${student_name}`,
		size: 'small',
		fields: [{ fieldtype: 'Attach', fieldname: 'answer_sheet_image', label: 'Answer Sheet (photo)', reqd: 1 }],
		primary_action_label: 'Grade with AI',
		primary_action: function (values) {
			frappe.call({
				method: 'ai_education_suite.ai_core.api.image_grading.grade_from_images',
				args: Object.assign(
					{ answer_sheet_image: values.answer_sheet_image, student: student, course: course },
					paper_ref
				),
				freeze: true,
				freeze_message: 'Grading with AI…',
				callback: function (r) {
					dialog.hide();
					if (!r.message) return;
					ai_edu_show_grading_results(r.message);
				},
			});
		},
	});
	dialog.show();
}

function ai_edu_show_grading_results(payload) {
	const results = payload.results || [];
	const dialog = new frappe.ui.Dialog({
		title: `Graded ${results.length} Question(s)`,
		size: 'large',
		fields: [{ fieldtype: 'HTML', fieldname: 'results_html' }],
	});
	const html =
		results
			.map(function (item, i) {
				const name = (payload.created || [])[i];
				return `
					<div class="ai-edu-list-row" data-doctype="AI Grading Suggestion" data-name="${name || ''}">
						<div>
							<div class="ai-edu-list-title">Q${item.question_number || i + 1}: ${item.suggested_score ?? 0} / ${item.max_score ?? 0}</div>
							<div class="ai-edu-list-sub">${frappe.utils.escape_html(item.rationale || '')}</div>
						</div>
						${name ? '<button class="btn btn-xs btn-default ai-edu-open-btn">Open →</button>' : ''}
					</div>
				`;
			})
			.join('') || '<p class="text-muted">No questions were graded.</p>';
	dialog.fields_dict.results_html.$wrapper.html(`<div class="ai-edu-list">${html}</div>`);
	dialog.fields_dict.results_html.$wrapper.on('click', '.ai-edu-open-btn', function () {
		const $row = $(this).closest('.ai-edu-list-row');
		frappe.set_route('Form', $row.data('doctype'), $row.data('name'));
		dialog.hide();
	});
	dialog.show();
}

function ai_edu_show_generate_paper_dialog() {
	const dialog = new frappe.ui.Dialog({
		title: 'Generate Question Paper from Material',
		size: 'small',
		fields: [
			{ fieldtype: 'Link', fieldname: 'course', label: 'Course', options: 'Course', reqd: 1 },
			{ fieldtype: 'Link', fieldname: 'student_group', label: 'Student Group (optional)', options: 'Student Group' },
			{
				fieldtype: 'Attach', fieldname: 'material_file',
				label: 'Teaching Material (PDF or DOCX)', reqd: 1,
			},
			{
				fieldtype: 'Select', fieldname: 'mode', label: 'Question Selection',
				options: 'Class Performance (default)\nEasy\nMedium\nHard',
				default: 'Class Performance (default)', reqd: 1,
			},
			{
				fieldtype: 'Int', fieldname: 'num_questions', label: 'Number of Questions',
				default: 10, reqd: 1,
			},
		],
		primary_action_label: 'Generate Paper',
		primary_action: function (values) {
			const mode_map = {
				'Class Performance (default)': 'class_performance',
				Easy: 'easy',
				Medium: 'medium',
				Hard: 'hard',
			};
			frappe.call({
				method: 'ai_education_suite.ai_core.api.material_paper.generate_question_paper_from_material',
				args: {
					file_url: values.material_file,
					course: values.course,
					student_group: values.student_group,
					num_questions: values.num_questions,
					mode: mode_map[values.mode] || 'class_performance',
				},
				freeze: true,
				freeze_message: 'Reading material and generating questions…',
				callback: function (r) {
					dialog.hide();
					if (!r.message || !r.message.name) return;
					frappe.show_alert({ message: 'Question paper generated.', indicator: 'green' });
					ai_edu_show_question_paper_preview(r.message.name);
				},
			});
		},
	});
	dialog.show();
}

function ai_edu_show_manage_houses_dialog() {
	const dialog = new frappe.ui.Dialog({
		title: 'Manage Houses',
		size: 'large',
		fields: [
			{ fieldtype: 'Data', fieldname: 'new_house_name', label: 'House Name' },
			{ fieldtype: 'Data', fieldname: 'new_color_code', label: 'Color (hex, e.g. #e53935)' },
			{ fieldtype: 'Int', fieldname: 'new_capacity', label: 'Capacity', default: 100 },
			{ fieldtype: 'Column Break' },
			{ fieldtype: 'HTML', fieldname: 'houses_html' },
		],
		primary_action_label: '+ Add House',
		primary_action: function (values) {
			if (!values.new_house_name) {
				frappe.show_alert({ message: 'House name is required.', indicator: 'red' });
				return;
			}
			frappe.call({
				method: 'frappe.client.insert',
				args: {
					doc: {
						doctype: 'House',
						house_name: values.new_house_name,
						color_code: values.new_color_code,
						capacity: values.new_capacity,
					},
				},
				callback: function () {
					dialog.set_value('new_house_name', '');
					dialog.set_value('new_color_code', '');
					ai_edu_load_houses_list(dialog);
				},
			});
		},
	});
	ai_edu_load_houses_list(dialog);
	dialog.show();
}

function ai_edu_load_houses_list(dialog) {
	frappe.call({
		method: 'frappe.client.get_list',
		args: {
			doctype: 'House',
			fields: ['name', 'house_name', 'color_code', 'capacity'],
			limit_page_length: 50,
		},
		callback: function (r) {
			const rows = r.message || [];
			const html =
				rows
					.map(function (row) {
						return `
							<div class="ai-edu-list-row" data-name="${row.name}">
								<div>
									<div class="ai-edu-list-title">
										<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${row.color_code || '#ccc'};margin-right:6px;"></span>
										${frappe.utils.escape_html(row.house_name || row.name)}
									</div>
									<div class="ai-edu-list-sub">Capacity: ${row.capacity || 0}</div>
								</div>
								<button class="btn btn-xs btn-default ai-edu-open-btn">Open →</button>
							</div>
						`;
					})
					.join('') || '<p class="text-muted">No houses yet \u2014 add one on the left.</p>';
			dialog.fields_dict.houses_html.$wrapper.html(`<div class="ai-edu-list">${html}</div>`);
			dialog.fields_dict.houses_html.$wrapper.off('click', '.ai-edu-open-btn').on('click', '.ai-edu-open-btn', function () {
				const name = $(this).closest('.ai-edu-list-row').data('name');
				frappe.set_route('Form', 'House', name);
				dialog.hide();
			});
		},
	});
}

let ai_edu_chat_context = null;

function ai_edu_get_result_label(row) {
	return row.student || row.title || row.applicant_name || row.student_name || row.name;
}

function ai_edu_send_chat_query($body) {
	const $input = $body.find('#ai-edu-chat-input');
	const query_text = ($input.val() || '').trim();
	if (!query_text) return;
	$input.val('');
	ai_edu_append_chat_message($body, query_text, 'user');
	const $thinking = ai_edu_append_chat_message($body, 'Thinking…', 'ai');

	frappe.call({
		method: 'ai_education_suite.query_assistant.api.ask',
		args: {
			query_text: query_text,
			context: ai_edu_chat_context ? JSON.stringify(ai_edu_chat_context) : null,
		},
		callback: function (r) {
			$thinking.remove();
			if (!r.message) {
				ai_edu_append_chat_message($body, "Sorry, I couldn't process that.", 'ai');
				return;
			}
			const msg = r.message;
			const count_label = `${msg.count} result${msg.count === 1 ? '' : 's'}`;
			ai_edu_append_chat_message($body, `${msg.explanation || ''} (${count_label})`, 'ai');
			if (msg.results && msg.results.length) {
				ai_edu_append_chat_results($body, msg.doctype, msg.results);
				// Remember this turn so a follow-up like "this applicant" or
				// "that student" can be resolved against it next time.
				ai_edu_chat_context = {
					doctype: msg.doctype,
					results: msg.results.slice(0, 10).map(function (row) {
						return { name: row.name, label: ai_edu_get_result_label(row) };
					}),
				};
			} else {
				ai_edu_chat_context = null;
			}
		},
		error: function () {
			$thinking.remove();
			ai_edu_append_chat_message($body, 'Something went wrong answering that — check that AI Settings has a valid Groq key.', 'ai');
		},
	});
}

function ai_edu_append_chat_message($body, text, who) {
	const $messages = $body.find('#ai-edu-chat-messages');
	const $msg = $(`<div class="ai-edu-chat-msg ai-edu-chat-msg-${who}"></div>`).text(text);
	$messages.append($msg);
	$messages.scrollTop($messages[0].scrollHeight);
	return $msg;
}

function ai_edu_append_chat_results($body, doctype, results) {
	const $messages = $body.find('#ai-edu-chat-messages');
	const label_keys = ['name', 'student', 'title', 'applicant_name', 'student_name'];
	const rows = results
		.slice(0, 8)
		.map(function (row) {
			const label = ai_edu_get_result_label(row);
			const detail_bits = Object.keys(row)
				.filter(function (k) {
					return label_keys.indexOf(k) === -1 && row[k] !== null && row[k] !== undefined && row[k] !== '';
				})
				.map(function (k) {
					const field_label = frappe.model && frappe.model.unscrub ? frappe.model.unscrub(k) : k;
					return `<div class="ai-edu-chat-result-detail"><b>${frappe.utils.escape_html(field_label)}:</b> ${frappe.utils.escape_html(String(row[k]))}</div>`;
				})
				.join('');
			return `
				<div class="ai-edu-chat-result-row" data-doctype="${doctype}" data-name="${row.name}">
					<div class="ai-edu-chat-result-title">${frappe.utils.escape_html(String(label))}</div>
					${detail_bits}
				</div>
			`;
		})
		.join('');
	const $block = $(`<div class="ai-edu-chat-msg ai-edu-chat-msg-ai ai-edu-chat-results">${rows}</div>`);
	$messages.append($block);
	$messages.scrollTop($messages[0].scrollHeight);
	$block.on('click', '.ai-edu-chat-result-row', function () {
		frappe.set_route('Form', $(this).data('doctype'), $(this).data('name'));
	});
}

function inject_ai_edu_styles() {
	if (document.getElementById('ai-edu-dashboard-styles')) return;
	const style = document.createElement('style');
	style.id = 'ai-edu-dashboard-styles';
	style.innerHTML = `
		.ai-edu-dashboard { background:#0b1220; color:#e2e8f0; padding:24px; border-radius:8px; }
		.ai-edu-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; }
		.ai-edu-title { font-size:20px; font-weight:700; letter-spacing:0.5px; }
		.ai-edu-subtitle { color:#94a3b8; font-size:13px; margin-top:2px; }
		.ai-edu-status { color:#34d399; font-size:12px; letter-spacing:1px; text-transform:uppercase; display:flex; align-items:center; gap:6px; }
		.ai-edu-dot { width:8px; height:8px; border-radius:50%; background:#34d399; display:inline-block; }
		.ai-edu-actions-row { display:flex; gap:12px; margin-bottom:24px; flex-wrap:wrap; }
		.ai-edu-action-btn { background:#1d4ed8 !important; color:#fff !important; border:1px solid #1e3a8a !important; font-weight:600; padding:10px 16px !important; border-radius:8px !important; }
		.ai-edu-action-btn:hover { background:#1e40af !important; }
		.ai-edu-action-btn:nth-of-type(2) { background:#7c3aed !important; border-color:#5b21b6 !important; }
		.ai-edu-action-btn:nth-of-type(2):hover { background:#6d28d9 !important; }
		.ai-edu-action-btn:nth-of-type(3) { background:#059669 !important; border-color:#065f46 !important; }
		.ai-edu-action-btn:nth-of-type(3):hover { background:#047857 !important; }
		.ai-edu-kpi-row { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:16px; margin-bottom:24px; }
		.ai-edu-kpi-card { background:#111827; border:1px solid #1f2937; border-radius:10px; padding:18px; cursor:pointer; transition:transform .15s, border-color .15s; border-top:3px solid var(--kpi-color, #38bdf8); }
		.ai-edu-kpi-card:hover { transform:translateY(-2px); border-color:#334155; }
		.ai-edu-kpi-icon { font-size:20px; opacity:0.85; margin-bottom:8px; }
		.ai-edu-kpi-value { font-size:28px; font-weight:700; font-family:'Courier New', monospace; }
		.ai-edu-kpi-label { color:#94a3b8; font-size:12px; text-transform:uppercase; letter-spacing:0.5px; margin-top:4px; }
		.ai-edu-insight-card { background:#111827; border:1px solid #1f2937; border-radius:10px; padding:20px; }
		.ai-edu-insight-header { display:flex; justify-content:space-between; align-items:center; color:#94a3b8; font-size:12px; letter-spacing:1px; text-transform:uppercase; margin-bottom:12px; }
		.ai-edu-insight-text { color:#cbd5e1; line-height:1.6; font-size:14px; }
		.ai-edu-more-section { margin-top:20px; }
		.ai-edu-more-header { color:#64748b; font-size:11px; letter-spacing:1px; text-transform:uppercase; margin-bottom:10px; }
		.ai-edu-more-row { display:flex; flex-wrap:wrap; gap:10px; }
		.ai-edu-more-link { background:#111827; border:1px solid #1f2937; color:#94a3b8; font-size:13px; padding:8px 14px; border-radius:20px; cursor:pointer; transition:background .15s,color .15s; }
		.ai-edu-more-link:hover { background:#1e293b; color:#e2e8f0; }
		.ai-edu-chat-card { background:#111827; border:1px solid #1f2937; border-radius:10px; padding:16px; margin-bottom:20px; }
		.ai-edu-chat-header { color:#94a3b8; font-size:12px; letter-spacing:1px; text-transform:uppercase; margin-bottom:10px; }
		.ai-edu-chat-messages { max-height:220px; overflow-y:auto; display:flex; flex-direction:column; gap:8px; margin-bottom:10px; padding-right:4px; }
		.ai-edu-chat-msg { max-width:80%; padding:8px 12px; border-radius:10px; font-size:13px; line-height:1.5; }
		.ai-edu-chat-msg-user { align-self:flex-end; background:#1d4ed8; color:#fff; }
		.ai-edu-chat-msg-ai { align-self:flex-start; background:#1e293b; color:#e2e8f0; }
		.ai-edu-chat-results { display:flex; flex-direction:column; gap:4px; }
		.ai-edu-chat-result-row { background:#111827; border:1px solid #334155; border-radius:6px; padding:8px 10px; cursor:pointer; }
		.ai-edu-chat-result-row:hover { background:#1e293b; }
		.ai-edu-chat-result-title { font-weight:600; margin-bottom:2px; }
		.ai-edu-chat-result-detail { font-size:12px; color:#94a3b8; line-height:1.4; }
		.ai-edu-chat-result-detail b { color:#cbd5e1; }
		.ai-edu-chat-input-row { display:flex; gap:8px; }
		.ai-edu-chat-input-row input { background:#0b1220 !important; color:#e2e8f0 !important; border:1px solid #334155 !important; }
		.ai-edu-paper-status { background:#0f2130; border:1px solid #1e3a5f; border-radius:8px; padding:10px 14px; font-size:13px; color:#cbd5e1; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; gap:10px; }
		.ai-edu-btn { background:#1e293b !important; color:#e2e8f0 !important; border:1px solid #334155 !important; }
		.ai-edu-loading { color:#64748b; padding:20px; }
		.ai-edu-list-row { display:flex; justify-content:space-between; align-items:center; padding:12px; border-bottom:1px solid #eee; }
		.ai-edu-list-row:hover { background:#f8f9fa; }
		.ai-edu-list-title { font-weight:600; }
		.ai-edu-list-sub { color:#888; font-size:12px; }
		.ai-edu-doc-page { background:#fff; color:#111; font-family:Georgia,'Times New Roman',serif; padding:40px; box-shadow:0 0 12px rgba(0,0,0,0.15); max-width:650px; margin:0 auto; }
		.ai-edu-doc-title { font-size:20px; font-weight:700; text-align:center; }
		.ai-edu-doc-meta-line { text-align:center; font-style:italic; color:#555; margin-top:4px; font-size:13px; }
		.ai-edu-doc-q { margin-bottom:14px; font-size:14px; line-height:1.5; }
		.ai-edu-doc-meta { color:#666; font-size:11px; font-style:italic; }
	`;
	document.head.appendChild(style);
}

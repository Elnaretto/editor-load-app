from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import plotly.express as px
import plotly.io as pio
import pandas as pd
import io
from openpyxl import Workbook
import os


app = Flask(__name__)

# Подключение к базе данных через переменную окружения
db_url = os.environ.get("DATABASE_URL")

if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if not db_url:
    db_url = 'sqlite:///load_data.db'

if "postgresql" in db_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url + "?sslmode=require"
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url

db = SQLAlchemy(app)
from flask_migrate import Migrate


migrate = Migrate(app, db)

class Chief(db.Model):
    __tablename__ = 'chief'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    editors = db.relationship('Editor', backref='chief', lazy=True)

class Editor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String, unique=True, nullable=False)
    fte = db.Column(db.Float, default=1.0)
    chief_id = db.Column(db.Integer, db.ForeignKey('chief.id'), nullable=False)
    loads = db.relationship('LoadEntry', backref='editor', lazy=True)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    priority = db.Column(db.String, default='medium')
    loads = db.relationship('LoadEntry', backref='project', lazy=True)

class LoadEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    editor_id = db.Column(db.Integer, db.ForeignKey('editor.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    hours = db.Column(db.Float, nullable=False)

def seed_db():
    # Создаем шефов и редакторов, если их нет
    if Chief.query.count() == 0:
        chiefs_data = {
            "ЭЛЬНАР БАЙНАЗАРОВ": [
                ("mishapomer", 1), ("marytrip4", 1), ("olialo", 1), ("lavhap", 1),
                ("matveevahelen", 0.75), ("aaperminova", 1), ("zzztana", 1),
                ("e-litvinova1", 0.5), ("elenakupr", 1), ("sazonovaiv", 1)
            ],
            "САША МОЖГИНА": [
                ("tatyana-ekt",1), ("xeniabarnie",1), ("ivanshipnigov",1),
                ("dbudantseva",1), ("petrukhinadv",0.5), ("mariantos",0.5),
                ("vystorop",0.75), ("evdonat",1), ("remezanechka",1)
            ],
            "САША ЛАПИНА": [
                ("eklaving",0.5), ("geondta",1), ("goldinovaag",1),
                ("mariyapender",0.5), ("olgayasko",1), ("sasmr",1),
                ("sofiamell2019",0.5), ("tnevidimova",1), ("tatotch",1)
            ],
            "ЖЕНЯ ВОРОПАЕВА": [
                ("var-ki",1), ("arychagova28",0.5), ("dimaruma",0.5),
                ("sergeikiselev",1), ("dmsynytsyn",1), ("annatalyzina",1),
                ("liza-grimm",1), ("kovaleveliz23",1), ("egorovakateai",1)
            ],
            "ИРА СМИРНОВА": [
                ("yeliseeva89",1), ("sofiatishina",1), ("adiann",1),
                ("fateeva-nina",1), ("klyutarevich",1), ("timirolga",0.75),
                ("pellenen",1), ("elizasid",1), ("anna-hoteeva",1)
            ],
            "ЭРИКА ГОВОРУНОВА": [
                ("humanvice",1), ("p-leoneed",0.5), ("pakatt",1),
                ("vkudrikova",1), ("opstasenko",1), ("ddrogozhina",1),
                ("anastasiaemel",0.5), ("elenashults",1), ("juvolobueva",0.5),
                ("agoncharskaya",1), ("irenever",1)
            ],
            "ОЛЯ МАРЕЕВА": [
                ("opudovkina",1), ("platonovalina",0.5), ("petelinao",0.5),
                ("priannik",1), ("shaposh-k-s",1), ("tsurik7",0.5),
                ("losev78",1), ("elmamontova",1), ("ngrelya",1), ("iradeslab",1)
            ],
            "НАТАША ЕНА": [
                ("alexraspopin",1), ("aver-kir",1), ("bakerkina",1),
                ("serebriakovad",1), ("elchent",1), ("tkriukova",0),
                ("raidugina",1), ("sofiyaptr",0.5)
            ],
        }

        for chief_name, editors_list in chiefs_data.items():
            chief = Chief(name=chief_name)
            db.session.add(chief)
            db.session.flush()  # Чтобы получить chief.id

            for login, fte in editors_list:
                editor = Editor(login=login, fte=fte, chief_id=chief.id)
                db.session.add(editor)

        db.session.commit()

    # Создаем проекты, если их нет
    if Project.query.count() == 0:
        project_names = [
            "Функции", "Билингва", "Муза", "Файлы",
            "Тьютор", "Память", "Этика", "Этика Переписи",
            "СБС", "Аннотации"
        ]
        for pname in project_names:
            p = Project(name=pname)
            db.session.add(p)
        db.session.commit()
        
@app.route('/initdb')
def initdb():
    db.create_all()
    return "База данных создана!"
       

@app.route('/')
def index():
    chiefs = Chief.query.all()
    projects = Project.query.all()
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    return render_template('index.html', chiefs=chiefs, projects=projects, today=today_str)

@app.route('/editors_for_chief/<int:chief_id>')
def editors_for_chief(chief_id):
    editors = Editor.query.filter_by(chief_id=chief_id).all()
    editors_data = [{"id": e.id, "login": e.login} for e in editors]
    return jsonify(editors_data)

@app.route('/submit_loads', methods=['POST'])
def submit_loads():
    data = request.json  # ожидаем JSON на вход
    editor_id = int(data['editor'])
    date_str = data['date']
    date = datetime.strptime(date_str, '%Y-%m-%d').date()

    projects = Project.query.all()

    # Сохраняем приоритеты
    for project in projects:
        priority_key = f'priority_{project.id}'
        if priority_key in data:
            new_priority = data[priority_key]
            if new_priority != project.priority:
                project.priority = new_priority

    # Обрабатываем часы с корректировкой
    for project in projects:
        hours_key = f"hours_{project.id}"
        if hours_key in data and str(data[hours_key]).strip():
            try:
                delta_hours = float(data[hours_key])
            except ValueError:
                continue

            load_entry = LoadEntry.query.filter_by(
                editor_id=editor_id,
                project_id=project.id,
                date=date
            ).first()

            if load_entry:
                new_hours = load_entry.hours + delta_hours
                if new_hours <= 0:
                    db.session.delete(load_entry)
                else:
                    load_entry.hours = new_hours
            else:
                if delta_hours > 0:
                    load_entry = LoadEntry(
                        editor_id=editor_id,
                        project_id=project.id,
                        date=date,
                        hours=delta_hours
                    )
                    db.session.add(load_entry)

    db.session.commit()

    # Вернем обновленные нагрузки сразу после изменения
    updated_loads = LoadEntry.query.filter_by(editor_id=editor_id, date=date).all()
    result = []
    for load in updated_loads:
        result.append({
            'project_id': load.project_id,
            'hours': load.hours
        })

    return jsonify({'message': 'Обновлено', 'loads': result})

@app.route('/get_loads/<int:editor_id>/<date_str>')
def get_loads(editor_id, date_str):
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    loads = LoadEntry.query.filter_by(editor_id=editor_id, date=date).all()
    data = []
    for load in loads:
        data.append({
            'project_id': load.project_id,
            'hours': load.hours
        })
    return jsonify(data)


@app.route('/add_project', methods=['POST'])
def add_project():
    data = request.json
    name = data.get('name')
    priority = data.get('priority', 'medium')

    if not name:
        return jsonify({'error': 'Название проекта обязательно'}), 400

    existing = Project.query.filter_by(name=name).first()
    if existing:
        return jsonify({'error': 'Проект с таким именем уже существует'}), 400

    new_project = Project(name=name, priority=priority)
    db.session.add(new_project)
    db.session.commit()

    return jsonify({'message': 'Проект добавлен', 'project': {'id': new_project.id, 'name': new_project.name, 'priority': new_project.priority}})
@app.route('/export_excel')
def export_excel():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        return "Пожалуйста, укажите обе даты", 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        return "Неверный формат даты", 400

    if start_date > end_date:
        return "Начальная дата не может быть больше конечной", 400

    # Запрос из базы по выбранному периоду
    loads = db.session.query(LoadEntry, Editor, Project)\
        .join(Editor).join(Project)\
        .filter(LoadEntry.date >= start_date, LoadEntry.date <= end_date)\
        .all()

    # Формируем словарь: project -> hours, editors (set)
    data = {}
    for load, editor, project in loads:
        if project.name not in data:
            data[project.name] = {"hours": 0, "editors": set()}
        data[project.name]["hours"] += load.hours
        data[project.name]["editors"].add(editor.login)

    # Создаем Excel файл в памяти
    wb = Workbook()
    ws = wb.active
    ws.title = "Отчет по проектам"

    # Заголовки
    ws.append(["Проект", "Нагрузка (часов)", "Количество редакторов", "Логины редакторов"])

    for project_name, info in data.items():
        editors_list = ", ".join(sorted(info["editors"]))
        ws.append([project_name, info["hours"], len(info["editors"]), editors_list])

    # Сохраняем в BytesIO
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"load_report_{start_date_str}_to_{end_date_str}.xlsx"

    return send_file(output,
                     as_attachment=True,
                     download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/visualization', methods=['GET', 'POST'])
def visualization():
    chiefs = Chief.query.all()
    selected_chief_id = request.args.get('chief_id', type=int)
    load_results = LoadResult.query.all()

    if selected_chief_id is None:
        selected_chief_id = 0  # по умолчанию показываем всю редакцию

    if selected_chief_id == 0:
        editors = Editor.query.all()
        chief_name = "Вся редакция"
    else:
        chief = Chief.query.get(selected_chief_id)
        if not chief:
            return "<h3>Выберите корректного шефа</h3>"
        editors = chief.editors
        chief_name = chief.name

    editor_ids = [e.id for e in editors]

    loads = db.session.query(LoadEntry, Editor, Project)\
        .join(Editor).join(Project)\
        .filter(LoadEntry.editor_id.in_(editor_ids)).all()

    if not loads:
        return render_template('visualization.html', chiefs=chiefs, selected_chief_id=selected_chief_id,
                               graph_html=None, message="Нет данных для выбранного шефа.")

    rows = []
    for load, editor, project in loads:
        rows.append({
            "project": project.name,
            "editor": editor.login,
            "hours": load.hours
        })

    df = pd.DataFrame(rows)

    df_grouped = df.groupby(['project', 'editor'], as_index=False).sum()

    df_summary = df_grouped.groupby('project').agg(
        total_hours=pd.NamedAgg(column='hours', aggfunc='sum'),
        editors_count=pd.NamedAgg(column='editor', aggfunc='nunique')
    ).reset_index()

    fig = px.bar(
        df_summary,
        x='project',
        y='total_hours',
        text=df_summary.apply(lambda row: f"{row.editors_count} редактор(ов)", axis=1),
        title=f"Нагрузка по проектам — {chief_name}",
        labels={'total_hours': 'Всего часов', 'project': 'Проект'},
        template="plotly_white"
    )
    fig.update_traces(textposition='outside')

    graph_html = pio.to_html(fig, full_html=False)

    details = {}
    for project in df_summary['project']:
        project_data = df_grouped[df_grouped['project'] == project]
        details[project] = [{
            'editor': row['editor'],
            'hours': row['hours']
        } for idx, row in project_data.iterrows()]

    # Загрузка сохранённых результатов нагрузки
    import json
    saved_results = []
    for r in load_results:
        try:
            load_data = json.loads(r.data)
        except Exception:
            load_data = r.data
        saved_results.append({
            'editor_id': r.editor_id,
            'date': r.date.strftime('%Y-%m-%d'),
            'load_data': load_data
        })

    return render_template('visualization.html', chiefs=chiefs, selected_chief_id=selected_chief_id,
                           graph_html=graph_html, details=details, message=None,
                           saved_results=saved_results)



@app.route('/update_priority', methods=['POST'])
def update_priority():
    projects = Project.query.all()
    for project in projects:
        field_name = f'priority_{project.id}'
        if field_name in request.form:
            new_priority = request.form[field_name]
            if new_priority != project.priority:
                project.priority = new_priority
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/visualization_timeline')
def visualization_timeline():
    loads = db.session.query(LoadEntry, Editor, Project)\
        .join(Editor).join(Project).all()

    rows = []
    for load, editor, project in loads:
        if not load.date:
            continue
        rows.append({
            "project": project.name,
            "editor": editor.login,
            "date": load.date,
            "hours": load.hours
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return render_template("visualization.html", graph_html=None, message="Нет данных по датам.")

    df_grouped = df.groupby(["date", "project"]).agg(
        total_hours=pd.NamedAgg(column="hours", aggfunc="sum"),
        editor_count=pd.NamedAgg(column="editor", aggfunc=lambda x: x.nunique())
    ).reset_index()

    fig = px.line(
        df_grouped,
        x="date",
        y="total_hours",
        color="project",
        markers=True,
        hover_data={"editor_count": True},
        labels={"total_hours": "Часы", "date": "Дата"},
        title="Динамика загрузки по проектам"
    )
    fig.update_layout(hovermode="x unified")

    graph_html = pio.to_html(fig, full_html=False)

    return render_template("visualization.html",
                           graph_html=graph_html,
                           details={},
                           message=None,
                           chiefs=[], selected_chief_id=None)

@app.route('/delete_loads', methods=['POST'])
def delete_loads():
    data = request.get_json()
    editor_id = data.get('editor_id')
    date_str = data.get('date', None)  # может быть None

    if not editor_id:
        return jsonify({'error': 'Не указан редактор'}), 400

    # Проверим, что редактор существует
    editor = Editor.query.get(editor_id)
    if not editor:
        return jsonify({'error': 'Редактор не найден'}), 404

    if date_str:
        # Преобразуем дату из строки в datetime.date
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Неверный формат даты'}), 400

        # Удаляем нагрузку для редактора на конкретную дату
        deleted = db.session.query(LoadEntry).filter_by(editor_id=editor_id, date=date).delete()
    else:
        # Удаляем ВСЕ нагрузки редактора за все время
        deleted = db.session.query(LoadEntry).filter_by(editor_id=editor_id).delete()

    db.session.commit()

    return jsonify({'message': f'Удалено записей: {deleted}'})

# --- Новая таблица для сохранения результатов нагрузки (до 10 человек одновременно) ---
class LoadResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    editor_id = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False)
    data = db.Column(db.Text, nullable=False)  # Можно хранить JSON строку с нагрузкой
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# --- Сохраняем результаты нагрузки ---
@app.route('/save_load_result', methods=['POST'])
def save_load_result():
    data = request.json
    editor_id = data.get('editor_id')
    date_str = data.get('date')
    load_data = data.get('load_data')  # Ожидаем JSON строку или словарь

    if not editor_id or not date_str or not load_data:
        return jsonify({'error': 'editor_id, date и load_data обязательны'}), 400

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    existing = LoadResult.query.filter_by(editor_id=editor_id, date=date).first()

    # Преобразуем load_data в строку, если это dict
    import json
    if isinstance(load_data, dict):
        load_data = json.dumps(load_data)

    if existing:
        existing.data = load_data
    else:
        # Ограничиваем максимум 10 записей для разных редакторов/дат
        count = LoadResult.query.count()
        if count >= 10:
            # Можно по логике удалить старейшую запись
            oldest = LoadResult.query.order_by(LoadResult.updated_at.asc()).first()
            if oldest:
                db.session.delete(oldest)

        new_result = LoadResult(editor_id=editor_id, date=date, data=load_data)
        db.session.add(new_result)

    db.session.commit()
    return jsonify({'message': 'Результаты сохранены'})

# --- Получить сохранённые результаты нагрузки для отображения на второй странице ---
@app.route('/get_load_results', methods=['GET'])
def get_load_results():
    results = LoadResult.query.all()
    import json
    output = []
    for r in results:
        try:
            load_data = json.loads(r.data)
        except Exception:
            load_data = r.data  # если не json, то просто строка
        output.append({
            'editor_id': r.editor_id,
            'date': r.date.strftime('%Y-%m-%d'),
            'load_data': load_data
        })
    return jsonify(output)

@app.route('/visualization_editors')
def visualization_editors():
    # Получаем всех редакторов из базы, чтобы отдать в выпадающий список
    editors = Editor.query.order_by(Editor.login).all()
    today_str = date.today().isoformat()
    return render_template('visualization_editors.html', editors=editors, today=today_str)

@app.route('/get_editor_loads')
def get_editor_loads():
    editor_id = request.args.get('editor_id')
    date_str = request.args.get('date')

    if not editor_id or not date_str:
        return jsonify({'error': 'Не передан editor_id или date'}), 400

    # Преобразуем дату из строки в объект date
    try:
        date_obj = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({'error': 'Некорректный формат даты'}), 400

    # Выбираем нагрузки для этого редактора и даты
    loads = LoadEntry.query.filter_by(editor_id=editor_id, date=date_obj).all()

    result = []
    for load in loads:
        project = load.project  # SQLAlchemy связь
        result.append({
            'project_id': project.id,
            'project_name': project.name,
            'hours': load.hours
        })

    return jsonify({'loads': result})

# --- Запуск ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_db()
    app.run(debug=True)
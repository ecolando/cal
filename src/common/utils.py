import os
import json
import dateparser


DATA_DIR = 'data'
TEMPLATES_DIR = os.path.join('src', 'resources', 'templates')


def get_assignment_dict(title, course, due_date, link, submitted):
    return {
        'title': title,
        'course': course,
        'dueDate': dateparser.parse(due_date, settings={'RETURN_AS_TIMEZONE_AWARE': True}).isoformat(),
        'link': link,
        'submitted': submitted
    }


def load_template(name):
    with open(os.path.join(TEMPLATES_DIR, name), 'r') as file:
        return file.read()


def save_data(var_name, obj):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    target = os.path.join(DATA_DIR, var_name + '.js')
    with open(target, 'w', encoding='utf-8') as file:
        file.write(f'{var_name} = {json.dumps(obj, indent=2)};\n')

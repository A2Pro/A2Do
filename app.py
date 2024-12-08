from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# MongoDB setup
client = MongoClient('mongodb://localhost:27017/')
db = client['task_scheduler']
tasks_collection = db['tasks']

@app.route('/')
def index():
    return render_template('home.html')

@app.route('/tasks')
def tasks():
    try:
        # Get all tasks, sorted by start_date
        tasks = list(tasks_collection.find().sort('start_date', 1))
        today = datetime.now().strftime('%Y-%m-%d')
        return render_template('tasks.html', tasks=tasks, today=today)
    except Exception as e:
        flash('Error loading tasks: ' + str(e), 'error')
        return redirect(url_for('index'))

@app.route('/scheduler')
def scheduler():
    try:
        date_str = request.args.get('date')
        if date_str:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            selected_date = datetime.now()

        # Get the start and end of the selected month
        start_date = selected_date.replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)

        # Get all tasks for the selected month
        tasks = list(tasks_collection.find({
            'start_date': {
                '$gte': start_date,
                '$lt': end_date
            }
        }).sort('start_date', 1))

        # Calculate calendar dates
        calendar_weeks = generate_calendar_dates(selected_date)
        
        return render_template('scheduler.html',
                             tasks=tasks,
                             selected_date=selected_date,
                             calendar_weeks=calendar_weeks,
                             today=datetime.now().date(),
                             timedelta=timedelta)
    except Exception as e:
        flash('Error loading calendar: ' + str(e), 'error')
        return redirect(url_for('index'))

@app.route('/add_task', methods=['POST'])
def add_task():
    try:
        title = request.form.get('title')
        description = request.form.get('description')
        start_date = request.form.get('start_date')
        start_time = request.form.get('start_time')
        estimated_hours = int(request.form.get('estimated_hours', 0))
        estimated_minutes = int(request.form.get('estimated_minutes', 0))
        
        # Calculate total estimated time in minutes
        total_estimated_minutes = (estimated_hours * 60) + estimated_minutes
        
        # Create datetime object for start_date
        start_datetime = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M')
        
        # Create task document
        task = {
            'title': title,
            'description': description,
            'start_date': start_datetime,
            'estimated_time': total_estimated_minutes,
            'is_completed': False,
            'created_at': datetime.utcnow()
        }
        
        # Insert into MongoDB
        result = tasks_collection.insert_one(task)
        
        if result.inserted_id:
            flash('✅ Task added successfully!', 'success')
        else:
            flash('❌ Error adding task: Failed to insert', 'error')
            
    except Exception as e:
        flash('❌ Error adding task: ' + str(e), 'error')
    
    return redirect(url_for('tasks'))

@app.route('/view_day/<date>')
def view_day(date):
    try:
        selected_date = datetime.strptime(date, '%Y-%m-%d')
        start_of_day = selected_date.replace(hour=0, minute=0, second=0)
        end_of_day = selected_date.replace(hour=23, minute=59, second=59)
        
        # Query MongoDB for tasks on this day
        tasks = list(tasks_collection.find({
            'start_date': {
                '$gte': start_of_day,
                '$lte': end_of_day
            }
        }).sort('start_date', 1))
        
        return render_template('day_view.html', 
                             tasks=tasks, 
                             selected_date=selected_date)
    except Exception as e:
        flash('Error loading day view: ' + str(e), 'error')
        return redirect(url_for('scheduler'))

@app.route('/update_task_status/<task_id>')
def update_task_status(task_id):
    try:
        # Find the task and get its current status
        task = tasks_collection.find_one({'_id': ObjectId(task_id)})
        if task:
            # Toggle the is_completed status
            new_status = not task.get('is_completed', False)
            tasks_collection.update_one(
                {'_id': ObjectId(task_id)},
                {'$set': {'is_completed': new_status}}
            )
            flash('✅ Task status updated successfully!', 'success')
        else:
            flash('❌ Task not found', 'error')
    except Exception as e:
        flash('❌ Error updating task: ' + str(e), 'error')
    return redirect(request.referrer or url_for('tasks'))

@app.route('/delete_task/<task_id>')
def delete_task(task_id):
    try:
        result = tasks_collection.delete_one({'_id': ObjectId(task_id)})
        if result.deleted_count:
            flash('🗑️ Task deleted successfully!', 'success')
        else:
            flash('❌ Task not found', 'error')
    except Exception as e:
        flash('❌ Error deleting task: ' + str(e), 'error')
    return redirect(request.referrer or url_for('tasks'))

def generate_calendar_dates(date):
    first_day = date.replace(day=1)
    if first_day.month == 12:
        last_day = first_day.replace(year=first_day.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last_day = first_day.replace(month=first_day.month + 1, day=1) - timedelta(days=1)
    
    first_weekday = first_day.weekday()
    calendar_days = []
    week = []
    
    for i in range(first_weekday):
        week.append(None)
    
    for day in range(1, last_day.day + 1):
        if len(week) == 7:
            calendar_days.append(week)
            week = []
        week.append(date.replace(day=day))
    
    while len(week) < 7:
        week.append(None)
    if week:
        calendar_days.append(week)
    
    return calendar_days

if __name__ == '__main__':
    app.run(debug=True)
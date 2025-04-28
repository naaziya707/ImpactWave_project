from flask import Flask, render_template, redirect, url_for, session, flash, request
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, DateField, FileField
from wtforms.validators import DataRequired, Email, ValidationError
import bcrypt
from flask_mysqldb import MySQL
import re
import os
from werkzeug.utils import secure_filename
from MySQLdb.cursors import DictCursor
import uuid
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from flask import send_from_directory

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # Ensure this is not an empty string in production
app.config['MYSQL_DB'] = 'impact_db'
app.config['UPLOAD_FOLDER'] = 'static/images/'  # Folder to save uploaded images
app.secret_key = 'your_secret_key_here'  # Use a more secure key in production

mysql = MySQL(app)

donations = []

def allowed_file(filename):
    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Temporary storage for PDF directory (set your actual path)
pdf_directory = 'receipts'
if not os.path.exists(pdf_directory):
    os.makedirs(pdf_directory)

class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register")

    def validate_email(self, field):
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s", (field.data,))
        user = cursor.fetchone()
        cursor.close()
        if user:
            raise ValidationError('Email Already Taken')

    def validate_password(self, field):
        password = field.data
        if len(password) < 8:
            raise ValidationError("Password should be at least 8 characters long.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValidationError("Password should contain at least one special character.")

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class EventForm(FlaskForm):
    title = StringField('Event Title', validators=[DataRequired()])
    description = TextAreaField('Event Description', validators=[DataRequired()])
    date = DateField('Event Date', format='%Y-%m-%d', validators=[DataRequired()])
    location = StringField('Event Location', validators=[DataRequired()])
    image = FileField('Event Image')  # Add FileField for image upload
    submit = SubmitField('Add Event')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        
        if user:
            flash('Email Already Taken', 'error')
            return redirect(url_for('register'))

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                       (username, email, hashed_password))
        mysql.connection.commit()
        cursor.close()

        flash("Registration successful! Please log in.", 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            session['id'] = user[0]

            if email == 'naaziya@gmail.com':
                session['is_admin'] = True
                return redirect(url_for('dashboard'))
            else:
                session['is_admin'] = False
                return redirect(url_for('homepage'))
        else:
            flash("Login failed. Please check your email and password", 'error')
            return redirect(url_for('login'))

    return render_template('login.html', form=form)

@app.route('/dashboard')
def dashboard():
    if 'id' in session:
        cursor = mysql.connection.cursor()
        
        if session.get('is_admin'):
            cursor.execute("SELECT COUNT(*) FROM users WHERE email = 'naaziya@gmail.com'")
            admin_user_count = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM users WHERE email != 'naaziya@gmail.com'")
            normal_user_count = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM events")
            events_posted = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM event_registration")
            event_registrations = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM donations")
            total_donations = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM messages")
            message_count = cursor.fetchone()[0] or 0
            cursor.close()
            return render_template('dashboard.html',
                                   admin_user_count=admin_user_count,
                                   normal_user_count=normal_user_count,
                                   events_posted=events_posted,
                                   event_registrations=event_registrations,
                                   total_donations=total_donations,
                                   message_count=message_count,
                                   is_admin=True)
        else:
            return redirect(url_for('homepage'))

    return redirect(url_for('login'))

@app.route('/donations')
def donations():
    if 'id' in session:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM donations")
        donations_data = cursor.fetchall()
        cursor.close()
        return render_template('donations.html', donations=donations_data)
    return redirect(url_for('login'))

@app.route('/')
def homepage():
    return render_template('homepage.html')

@app.route('/donate')
def udonate():
    return render_template('udonate.html')

@app.route('/donation_form/<cause_name>', methods=['GET', 'POST'])
def donation_form(cause_name):
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form['name']
            email = request.form['email']
            amount = request.form['amount']
            payment_method = request.form['payment_method']
            cause = cause_name
            date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            receipt_id = str(uuid.uuid4())
            
            # If payment method is credit card, retrieve card details
            if payment_method == 'credit_card':
                card_number = request.form['card_number']
                expiry_date = request.form['expiry_date']
                cvv = request.form['cvv']
                # Add any necessary validation for credit card details here

            # Insert donation data into donations table
            cursor = mysql.connection.cursor()
            cursor.execute(
                "INSERT INTO donations (amount, category, date, receipt_info, payment_method) VALUES (%s, %s, %s, %s, %s)",
                (amount, cause, date, receipt_id, payment_method)
            )
            mysql.connection.commit()
            cursor.close()

            # Generate PDF receipt
            generate_receipt_pdf(receipt_id, name, email, amount, cause, date)

            # Redirect to receipt download page
            return redirect(url_for('download_receipt', receipt_id=receipt_id))

        except KeyError as e:
            # Handle missing form field error (consider logging this or notifying the user in some way)
            return redirect(url_for('donation_form', cause_name=cause_name))
        except Exception as e:
            # Handle unexpected errors (consider logging this)
            return redirect(url_for('donation_form', cause_name=cause_name))

    return render_template('donation_form.html', cause_name=cause_name)


def generate_receipt_pdf(receipt_id, name, email, amount, cause, date):
    pdf_path = os.path.join(pdf_directory, f'receipt_{receipt_id}.pdf')
    c = canvas.Canvas(pdf_path, pagesize=letter)

    # Organization details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(200, 750, "ImpactWave - Help a Noble Cause")
    c.setFont("Helvetica", 10)
    c.drawString(200, 735, "1234 Donation Street, City, Country")
    c.drawString(200, 720, "Phone: +123-456-7890 | Email: impactwave@donate.org")
    c.drawString(200, 705, "Website: www.ImpactWave.com")

    # Draw a line under the header
    c.setStrokeColor(colors.grey)
    c.line(50, 690, 550, 690)

    # Receipt title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 670, "Donation Receipt")

    # Donation details
    c.setFont("Helvetica", 11)
    c.drawString(50, 640, f"Receipt ID: {receipt_id}")
    c.drawString(50, 620, f"Name: {name}")
    c.drawString(50, 600, f"Email: {email}")
    c.drawString(50, 580, f"Donation Amount: ${amount}")
    c.drawString(50, 560, f"Cause Supported: {cause}")
    c.drawString(50, 540, f"Date: {date}")

    # Thank you note
    c.setFont("Helvetica-Oblique", 12)
    c.setFillColor(colors.darkblue)
    c.drawString(50, 510, "Thank you for your generous contribution!")

    # Footer
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    c.drawString(50, 470, "This donation is tax-deductible as allowed by law. Keep this receipt for your records.")
    c.drawString(50, 455, "Organization Tax ID: 12-3456789")

    c.save()

@app.route('/download_receipt/<receipt_id>')
def download_receipt(receipt_id):
    pdf_path = os.path.join(pdf_directory, f'receipt_{receipt_id}.pdf')
    if os.path.exists(pdf_path):
        flash('Your receipt has been generated and is now being downloaded.', 'success')
        return send_from_directory(pdf_directory, f'receipt_{receipt_id}.pdf', as_attachment=True)

    flash('Receipt not found.', 'error')
    return redirect(url_for('udonate'))  # Redirect to the general donation page if receipt not found
 # Redirect to donation form if receipt not found


@app.route('/about')
def uabout():
    return render_template('uabout.html')

@app.route('/eevents', methods=['GET'])
def uevents():
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute("SELECT * FROM events")
    events_data = cursor.fetchall()
    cursor.close()
    return render_template('uevents.html', events=events_data)

@app.route('/volunteer/<int:event_id>', methods=['GET', 'POST'])
def volunteer_form(event_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT title FROM events WHERE id = %s", (event_id,))
    event = cursor.fetchone()
    cursor.close()

    if request.method == 'POST':
        volunteer_name = request.form['name']
        volunteer_email = request.form['email']
        participant_no = request.form['participant_no']

        # Validate form data
        if not volunteer_name or not volunteer_email or not participant_no:
            flash("Please fill in all required fields.", "error")
            return redirect(url_for('volunteer_form', event_id=event_id))  # Redirect back to the same form

        # Insert data into the database if validation passes
        cursor = mysql.connection.cursor()
        cursor.execute(
            "INSERT INTO event_registration (name, email, participant_no, registration_date) VALUES (%s, %s, %s, NOW())", 
            (volunteer_name, volunteer_email, participant_no)
        )
        mysql.connection.commit()
        cursor.close()

        flash("Thank you for volunteering!", "success")
        return redirect(url_for('uevents'))

    return render_template('volunteer_form.html', event_name=event[0], event_id=event_id)


def valid_contact_data(form_data):
    # Check if required fields are present and not empty
    if not form_data.get('name') or not form_data.get('email') or not form_data.get('message'):
        return False
    # You can add more validation logic if needed (e.g., email format)
    return True

@app.route('/contact', methods=['GET', 'POST'])
def ucontact():
    if request.method == 'POST':
        if not valid_contact_data(request.form):
            flash('There was an error with your submission.', 'contact_error')
            return redirect(url_for('ucontact'))

        # Proceed with saving the feedback to the database
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO messages (name, email, message) VALUES (%s, %s, %s)", (name, email, message))
        mysql.connection.commit()
        cursor.close()

        flash('Your feedback has been submitted, thank you!', 'success')
        return redirect(url_for('ucontact'))

    return render_template('ucontact.html')


@app.route('/users')
def users():
    if 'id' in session:
        cursor = mysql.connection.cursor(DictCursor)
        cursor.execute("SELECT * FROM users WHERE email != 'naaziya@gmail.com'")
        users_data = cursor.fetchall()
        cursor.close()
        return render_template('users.html', users=users_data)
    return redirect(url_for('login'))

@app.route('/delete_user/<int:id>', methods=['POST'])
def delete_user(id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (id,))
    mysql.connection.commit()
    cursor.close()
    flash('User deleted successfully!', 'success')
    return redirect(url_for('users'))

@app.route('/events', methods=['GET', 'POST'])
def events():
    form = EventForm()
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute("SELECT * FROM events")
    events_data = cursor.fetchall()
    cursor.close()

    if form.validate_on_submit():
        title = form.title.data
        description = form.description.data
        date = form.date.data
        location = form.location.data

        if 'image' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            flash('File not allowed', 'error')
            return redirect(request.url)

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO events (title, description, date, location, image) VALUES (%s, %s, %s, %s, %s)",
                       (title, description, date, location, filename))
        mysql.connection.commit()
        cursor.close()

        flash('Event added successfully!', 'success')
        return redirect(url_for('events'))

    return render_template('events.html', form=form, events=events_data)

@app.route('/update_event/<int:event_id>', methods=['GET', 'POST'])
def update_event(event_id):
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
    event = cursor.fetchone()
    cursor.close()

    if not event:
        flash('Event not found!', 'error')
        return redirect(url_for('events'))

    form = EventForm(obj=event)

    if form.validate_on_submit():
        title = form.title.data
        description = form.description.data
        date = form.date.data
        location = form.location.data
        image = form.image.data

        filename = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE events SET title=%s, description=%s, date=%s, location=%s, image=%s WHERE id=%s",
                       (title, description, date, location, filename if image else event['image'], event_id))
        mysql.connection.commit()
        cursor.close()

        flash('Event updated successfully!', 'success')
        return redirect(url_for('events'))

    return render_template('update_event.html', form=form, event_id=event_id)

@app.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if 'id' not in session:
        flash('You need to log in to delete an event.', 'error')
        return redirect(url_for('login'))

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
        mysql.connection.commit()
        cursor.close()
        flash('Event deleted successfully!', 'success')
    except Exception as e:
        flash('An error occurred while deleting the event.', 'error')

    return redirect(url_for('events'))

@app.route('/messages')
def messages():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, name, email, message, submitted_at FROM messages")
    messages = cursor.fetchall()

    formatted_messages = []
    for message in messages:
        date_only = message[4].strftime("%Y-%m-%d")
        formatted_messages.append((message[0], message[1], message[2], message[3], date_only))

    cursor.close()
    return render_template('messages.html', messages=formatted_messages)

@app.route('/delete_message/<int:id>', methods=['POST'])
def delete_message(id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM messages WHERE id = %s", (id,))
    mysql.connection.commit()
    cursor.close()
    flash('Message deleted successfully!', 'success')
    return redirect(url_for('messages'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

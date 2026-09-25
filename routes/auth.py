from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from models.user import (
    get_user_by_email, get_user_by_id, create_user, verify_user_password
)
from models.pharmacy import create_pharmacy, get_pharmacy_by_user_id

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            if session.get('role') not in allowed_roles:
                flash('Access denied: You do not have permission to view this resource.', 'danger')
                return redirect(url_for('medicine.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif role == 'pharmacy':
            return redirect(url_for('pharmacy.dashboard'))
        return redirect(url_for('user.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Please provide both email and password.', 'danger')
            return render_template('login.html', email=email)

        user = get_user_by_email(email)
        if not user or not verify_user_password(user['password_hash'], password):
            flash('Invalid email or password.', 'danger')
            return render_template('login.html', email=email)

        if not user.get('is_active', 1):
            flash('Your account has been deactivated. Please contact support.', 'danger')
            return render_template('login.html', email=email)

        # Check pharmacy status if pharmacy role
        if user['role'] == 'pharmacy':
            pharmacy = get_pharmacy_by_user_id(user['id'])
            if pharmacy and pharmacy['status'] == 'pending':
                flash('Your pharmacy account is pending admin approval. You will receive access once approved.', 'warning')
                return render_template('login.html', email=email)
            elif pharmacy and pharmacy['status'] in ('rejected', 'deactivated'):
                flash(f'Your pharmacy registration is {pharmacy["status"]}. Please contact the administrator.', 'danger')
                return render_template('login.html', email=email)

        # Establish session
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_email'] = user['email']
        session['role'] = user['role']
        session['user_city'] = user.get('city')
        session['user_area'] = user.get('area')
        session['user_lat'] = user.get('latitude')
        session['user_lng'] = user.get('longitude')

        flash(f'Welcome back, {user["name"]}!', 'success')
        next_page = request.args.get('next')
        if next_page and not next_page.startswith('//') and not next_page.startswith('http'):
            return redirect(next_page)

        if user['role'] == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif user['role'] == 'pharmacy':
            return redirect(url_for('pharmacy.dashboard'))
        return redirect(url_for('user.dashboard'))

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('user.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        address = request.form.get('address', '').strip()
        area = request.form.get('area', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()

        # Validation
        errors = []
        if not name:
            errors.append('Full Name is required.')
        if not email or '@' not in email:
            errors.append('A valid email address is required.')
        if not phone or len(phone) < 10:
            errors.append('A valid 10-digit phone number is required.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        existing_user = get_user_by_email(email)
        if existing_user:
            errors.append('An account with this email already exists.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('register.html', form_data=request.form)

        user_id, err = create_user(
            name=name,
            email=email,
            phone=phone,
            password=password,
            role='user',
            address=address,
            area=area,
            city=city,
            state=state,
            pincode=pincode,
            latitude=latitude if latitude else None,
            longitude=longitude if longitude else None
        )

        if err:
            flash(f'Registration error: {err}', 'danger')
            return render_template('register.html', form_data=request.form)

        flash('Registration successful! Please log in to your new account.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')

@auth_bp.route('/pharmacy/register', methods=['GET', 'POST'])
def pharmacy_register():
    if 'user_id' in session:
        return redirect(url_for('medicine.index'))

    if request.method == 'POST':
        pharmacy_name = request.form.get('pharmacy_name', '').strip()
        owner_name = request.form.get('owner_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        address = request.form.get('address', '').strip()
        area = request.form.get('area', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        operating_hours = request.form.get('operating_hours', '8:00 AM - 10:00 PM').strip()
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()

        errors = []
        if not pharmacy_name:
            errors.append('Pharmacy Name is required.')
        if not owner_name:
            errors.append('Owner / Manager Name is required.')
        if not email or '@' not in email:
            errors.append('A valid email address is required.')
        if not phone or len(phone) < 10:
            errors.append('A valid contact phone number is required.')
        if not address or not city or not pincode:
            errors.append('Complete address, city, and pincode are required.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        if get_user_by_email(email):
            errors.append('An account with this email already exists.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('pharmacy_register.html', form_data=request.form)

        # Create user account with role='pharmacy'
        user_id, err = create_user(
            name=owner_name,
            email=email,
            phone=phone,
            password=password,
            role='pharmacy',
            address=address,
            area=area,
            city=city,
            state=state,
            pincode=pincode,
            latitude=latitude if latitude else None,
            longitude=longitude if longitude else None
        )

        if err:
            flash(f'Registration error: {err}', 'danger')
            return render_template('pharmacy_register.html', form_data=request.form)

        # Create pharmacy record with status='pending'
        pharm_id, pharm_err = create_pharmacy(
            user_id=user_id,
            pharmacy_name=pharmacy_name,
            owner_name=owner_name,
            phone=phone,
            email=email,
            address=address,
            area=area,
            city=city,
            state=state,
            pincode=pincode,
            latitude=latitude if latitude else None,
            longitude=longitude if longitude else None,
            operating_hours=operating_hours,
            status='pending',
            is_demo=0
        )

        if pharm_err:
            flash(f'Error creating pharmacy profile: {pharm_err}', 'danger')
            return render_template('pharmacy_register.html', form_data=request.form)

        flash('Pharmacy registration submitted successfully! Your account is currently Pending Approval by the Admin. You can log in once approved.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('pharmacy_register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('medicine.index'))

# REST API Auth Endpoints
@auth_bp.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required.'}), 400

    user = get_user_by_email(email)
    if not user or not verify_user_password(user['password_hash'], password):
        return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401

    if not user.get('is_active', 1):
        return jsonify({'success': False, 'message': 'Your account is deactivated.'}), 403

    if user['role'] == 'pharmacy':
        pharmacy = get_pharmacy_by_user_id(user['id'])
        if pharmacy and pharmacy['status'] == 'pending':
            return jsonify({'success': False, 'message': 'Pharmacy registration pending admin approval.'}), 403
        elif pharmacy and pharmacy['status'] != 'approved':
            return jsonify({'success': False, 'message': f'Pharmacy registration is {pharmacy["status"]}.'}), 403

    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']
    session['role'] = user['role']
    session['user_city'] = user.get('city')
    session['user_area'] = user.get('area')
    session['user_lat'] = user.get('latitude')
    session['user_lng'] = user.get('longitude')

    return jsonify({
        'success': True,
        'message': 'Login successful',
        'user': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role']
        }
    })

@auth_bp.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@auth_bp.route('/api/auth/session', methods=['GET'])
def api_session():
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'user_id': session['user_id'],
            'name': session.get('user_name'),
            'email': session.get('user_email'),
            'role': session.get('role'),
            'city': session.get('user_city'),
            'area': session.get('user_area'),
            'lat': session.get('user_lat'),
            'lng': session.get('user_lng')
        })
    return jsonify({'authenticated': False})

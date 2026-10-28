import math
import os
from datetime import date, datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager, UserMixin, current_user, login_required, login_user, logout_user
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__, instance_relative_config=True)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
app.config["DEMO_MODE"] = os.getenv("DEMO_MODE", "0").strip() == "1"
database_url = os.getenv("DATABASE_URL", "").strip()
app.config["SQLALCHEMY_DATABASE_URI"] = database_url or (
    "sqlite:///" + os.path.join(app.instance_path, "medrelay.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
os.makedirs(app.instance_path, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"

FACILITY_TYPES = ["Hospital", "Clinic", "Registered Pharmacy"]
URGENCY_LEVELS = ["Routine", "High", "Critical"]
FACILITY_STATUSES = ["Pending", "Approved", "Rejected", "Suspended"]


class Facility(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    facility_type = db.Column(db.String(40), nullable=False)
    registration_no = db.Column(db.String(100), nullable=False, unique=True)
    address = db.Column(db.String(250), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(12), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20), default="Pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    users = db.relationship("User", backref="facility", lazy=True)
    inventory_items = db.relationship("InventoryItem", backref="facility", lazy=True)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="facility_admin", nullable=False)
    facility_id = db.Column(db.Integer, db.ForeignKey("facility.id"))
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def is_active(self):
        return self.is_active_account

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    generic_name = db.Column(db.String(160), nullable=False, default="")
    strength = db.Column(db.String(80), nullable=False, default="")
    dosage_form = db.Column(db.String(80), nullable=False, default="Tablet")
    unit = db.Column(db.String(40), nullable=False, default="packs")
    medicine_code = db.Column(db.String(80), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    inventory_items = db.relationship("InventoryItem", backref="medicine", lazy=True)


class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    facility_id = db.Column(db.Integer, db.ForeignKey("facility.id"), nullable=False, index=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicine.id"), nullable=False, index=True)
    batch_number = db.Column(db.String(100), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    quantity_on_hand = db.Column(db.Integer, nullable=False, default=0)
    reserved_quantity = db.Column(db.Integer, nullable=False, default=0)
    stock_condition = db.Column(db.String(20), nullable=False, default="Usable")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def available_quantity(self):
        if self.stock_condition != "Usable" or self.expiry_date < date.today():
            return 0
        return max(0, self.quantity_on_hand - self.reserved_quantity)


class MedicineRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requesting_facility_id = db.Column(db.Integer, db.ForeignKey("facility.id"), nullable=False, index=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicine.id"), nullable=False)
    quantity_requested = db.Column(db.Integer, nullable=False)
    quantity_fulfilled = db.Column(db.Integer, nullable=False, default=0)
    urgency = db.Column(db.String(20), nullable=False, default="Routine")
    reason = db.Column(db.Text, nullable=False)
    required_by = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(25), nullable=False, default="Open")
    priority_score = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    requesting_facility = db.relationship("Facility", foreign_keys=[requesting_facility_id])
    medicine = db.relationship("Medicine")
    transfers = db.relationship("Transfer", backref="medicine_request", lazy=True)


class Transfer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("medicine_request.id"), nullable=False, index=True)
    supplier_facility_id = db.Column(db.Integer, db.ForeignKey("facility.id"), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey("inventory_item.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(25), nullable=False, default="Offered")
    note = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    accepted_at = db.Column(db.DateTime)
    dispatched_at = db.Column(db.DateTime)
    received_at = db.Column(db.DateTime)

    supplier_facility = db.relationship("Facility", foreign_keys=[supplier_facility_id])
    inventory_item = db.relationship("InventoryItem")


@app.context_processor
def inject_template_globals():
    return {"today": date.today()}


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def approved_facility_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            if not current_user.facility or current_user.facility.status != "Approved":
                flash("Your facility must be approved before using this feature.", "warning")
                return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def facility_user_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role == "admin" or not current_user.facility_id:
            abort(403)
        if current_user.facility.status != "Approved":
            flash("Your facility must be approved before using this feature.", "warning")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def calculate_priority(urgency, required_by):
    score = {"Routine": 10, "High": 30, "Critical": 50}.get(urgency, 10)
    now = datetime.utcnow()
    if required_by <= now:
        score += 25
    elif required_by <= now + timedelta(hours=6):
        score += 20
    elif required_by <= now + timedelta(hours=24):
        score += 10
    return score


def distance_km(a, b):
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    radius = 6371
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat = math.radians(b.latitude - a.latitude)
    dlon = math.radians(b.longitude - a.longitude)
    x = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(x), math.sqrt(max(0, 1 - x)))


def get_matches(med_request):
    """Simple, explainable matching: approved facility, exact medicine, usable stock, freshness."""
    items = (InventoryItem.query.join(Facility)
             .filter(InventoryItem.medicine_id == med_request.medicine_id,
                     Facility.status == "Approved",
                     Facility.id != med_request.requesting_facility_id,
                     InventoryItem.stock_condition == "Usable",
                     InventoryItem.expiry_date >= date.today())
             .all())
    matches = []
    for item in items:
        if item.available_quantity <= 0:
            continue
        km = distance_km(med_request.requesting_facility, item.facility)
        matches.append({"item": item, "distance": km})
    # Prioritize same-city options, then known/shorter distance, then fresher stock.
    matches.sort(key=lambda x: (
        x["item"].facility.city.lower() != med_request.requesting_facility.city.lower(),
        x["distance"] is None,
        x["distance"] if x["distance"] is not None else 999999,
        x["item"].updated_at
    ))
    return matches


@app.route("/")
def index():
    stats = {
        "facilities": Facility.query.filter_by(status="Approved").count(),
        "medicines": Medicine.query.count(),
        "open_requests": MedicineRequest.query.filter(
            MedicineRequest.status.in_(["Open", "Partially Fulfilled"])
        ).count(),
    }
    return render_template("index.html", stats=stats, demo_mode=app.config["DEMO_MODE"])


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        facility_name = request.form.get("facility_name", "").strip()
        facility_type = request.form.get("facility_type", "")
        registration_no = request.form.get("registration_no", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        pincode = request.form.get("pincode", "").strip()
        lat_text, lon_text = request.form.get("latitude", "").strip(), request.form.get("longitude", "").strip()

        required = [full_name, email, password, facility_name, facility_type, registration_no, address, city, state, pincode]
        if not all(required):
            flash("Please complete all required fields.", "danger")
        elif len(password) < 8:
            flash("Use a password with at least 8 characters.", "danger")
        elif facility_type not in FACILITY_TYPES:
            flash("Choose a valid facility type.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
        elif Facility.query.filter_by(registration_no=registration_no).first():
            flash("That registration reference is already registered.", "danger")
        else:
            try:
                lat = float(lat_text) if lat_text else None
                lon = float(lon_text) if lon_text else None
                if (lat is None) != (lon is None):
                    raise ValueError()
                if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError()
            except ValueError:
                flash("Latitude and longitude must both be valid numbers, or both be blank.", "danger")
                return render_template("register.html", facility_types=FACILITY_TYPES)

            facility = Facility(
                name=facility_name, facility_type=facility_type,
                registration_no=registration_no, address=address, city=city,
                state=state, pincode=pincode, latitude=lat, longitude=lon,
                status="Pending"
            )
            user = User(full_name=full_name, email=email, role="facility_admin")
            user.set_password(password)
            db.session.add(facility)
            db.session.flush()
            user.facility_id = facility.id
            db.session.add(user)
            db.session.commit()
            flash("Registration submitted. An administrator must approve your facility before you can manage stock or requests.", "success")
            return redirect(url_for("login"))
    return render_template("register.html", facility_types=FACILITY_TYPES)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.is_active_account and user.check_password(password):
            login_user(user)
            flash("Welcome back.", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect, or the account is disabled.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        pending = Facility.query.filter_by(status="Pending").count()
        open_requests = MedicineRequest.query.filter(
            MedicineRequest.status.in_(["Open", "Partially Fulfilled"])
        ).count()
        critical = MedicineRequest.query.filter_by(urgency="Critical").filter(
            MedicineRequest.status.in_(["Open", "Partially Fulfilled"])
        ).count()
        return render_template("dashboard_admin.html", pending=pending, open_requests=open_requests, critical=critical)

    facility = current_user.facility
    if not facility:
        abort(403)
    if facility.status != "Approved":
        return render_template("pending.html", facility=facility)
    inventory_count = InventoryItem.query.filter_by(facility_id=facility.id).count()
    requests = MedicineRequest.query.filter_by(requesting_facility_id=facility.id).order_by(
        MedicineRequest.created_at.desc()).limit(8).all()
    incoming_offers = Transfer.query.filter(
        Transfer.request_id.in_(
            db.session.query(MedicineRequest.id).filter_by(requesting_facility_id=facility.id)
        ), Transfer.status == "Offered"
    ).order_by(Transfer.created_at.desc()).all()
    outgoing_transfers = Transfer.query.filter_by(supplier_facility_id=facility.id).filter(
        Transfer.status.in_(["Accepted", "Dispatched"])
    ).order_by(Transfer.created_at.desc()).all()
    return render_template("dashboard_facility.html", facility=facility,
                           inventory_count=inventory_count, requests=requests,
                           incoming_offers=incoming_offers, outgoing_transfers=outgoing_transfers)


@app.route("/admin/facilities")
@admin_required
def admin_facilities():
    facilities = Facility.query.order_by(
        db.case((Facility.status == "Pending", 0), else_=1), Facility.created_at.desc()
    ).all()
    return render_template("admin_facilities.html", facilities=facilities)


@app.route("/admin/facilities/<int:facility_id>/<action>", methods=["POST"])
@admin_required
def facility_action(facility_id, action):
    facility = db.get_or_404(Facility, facility_id)
    actions = {"approve": "Approved", "reject": "Rejected", "suspend": "Suspended"}
    if action not in actions:
        abort(400)
    facility.status = actions[action]
    db.session.commit()
    flash(f"{facility.name} is now marked {facility.status.lower()}.", "success")
    return redirect(url_for("admin_facilities"))


@app.route("/medicines", methods=["GET", "POST"])
@approved_facility_required
def medicines():
    if request.method == "POST":
        if current_user.role not in ["admin", "facility_admin", "inventory_manager"]:
            abort(403)
        name = request.form.get("name", "").strip()
        generic_name = request.form.get("generic_name", "").strip()
        strength = request.form.get("strength", "").strip()
        dosage_form = request.form.get("dosage_form", "").strip()
        unit = request.form.get("unit", "").strip() or "packs"
        code = request.form.get("medicine_code", "").strip() or None
        if not name or not dosage_form:
            flash("Medicine name and dosage form are required.", "danger")
        elif code and Medicine.query.filter_by(medicine_code=code).first():
            flash("That medicine code already exists.", "danger")
        else:
            med = Medicine(name=name, generic_name=generic_name, strength=strength,
                           dosage_form=dosage_form, unit=unit, medicine_code=code)
            db.session.add(med)
            db.session.commit()
            flash("Medicine added to the shared catalogue.", "success")
            return redirect(url_for("medicines"))
    q = request.args.get("q", "").strip()
    query = Medicine.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Medicine.name.ilike(like), Medicine.generic_name.ilike(like),
                                 Medicine.strength.ilike(like)))
    catalogue = query.order_by(Medicine.name.asc()).all()
    return render_template("medicines.html", medicines=catalogue, q=q)


@app.route("/inventory")
@facility_user_required
def inventory():
    items = InventoryItem.query.filter_by(facility_id=current_user.facility_id).join(Medicine).order_by(
        Medicine.name.asc(), InventoryItem.expiry_date.asc()).all()
    return render_template("inventory.html", items=items)


@app.route("/inventory/add", methods=["GET", "POST"])
@facility_user_required
def inventory_add():
    if request.method == "POST":
        medicine_id = request.form.get("medicine_id", type=int)
        batch = request.form.get("batch_number", "").strip()
        expiry_text = request.form.get("expiry_date", "")
        quantity = request.form.get("quantity_on_hand", type=int)
        condition = request.form.get("stock_condition", "Usable")
        medicine = db.session.get(Medicine, medicine_id) if medicine_id else None
        try:
            expiry = date.fromisoformat(expiry_text)
        except ValueError:
            expiry = None
        if not medicine or not batch or not expiry or quantity is None or quantity < 0:
            flash("Enter a medicine, batch, valid expiry date, and non-negative quantity.", "danger")
        elif condition not in ["Usable", "Quarantined", "Damaged"]:
            flash("Choose a valid stock condition.", "danger")
        else:
            item = InventoryItem(facility_id=current_user.facility_id, medicine_id=medicine.id,
                                 batch_number=batch, expiry_date=expiry, quantity_on_hand=quantity,
                                 stock_condition=condition)
            db.session.add(item)
            db.session.commit()
            flash("Inventory item added.", "success")
            return redirect(url_for("inventory"))
    catalogue = Medicine.query.order_by(Medicine.name.asc()).all()
    return render_template("inventory_add.html", medicines=catalogue)


@app.route("/marketplace")
@facility_user_required
def marketplace():
    open_requests = MedicineRequest.query.filter(
        MedicineRequest.status.in_(["Open", "Partially Fulfilled"]),
        MedicineRequest.requesting_facility_id != current_user.facility_id
    ).order_by(MedicineRequest.priority_score.desc(), MedicineRequest.required_by.asc()).all()
    return render_template("marketplace.html", requests=open_requests)


@app.route("/requests")
@facility_user_required
def requests_list():
    own_requests = MedicineRequest.query.filter_by(
        requesting_facility_id=current_user.facility_id
    ).order_by(MedicineRequest.created_at.desc()).all()
    return render_template("requests.html", requests=own_requests)


@app.route("/requests/new", methods=["GET", "POST"])
@facility_user_required
def request_new():
    if request.method == "POST":
        medicine_id = request.form.get("medicine_id", type=int)
        quantity = request.form.get("quantity_requested", type=int)
        urgency = request.form.get("urgency", "")
        reason = request.form.get("reason", "").strip()
        required_text = request.form.get("required_by", "")
        medicine = db.session.get(Medicine, medicine_id) if medicine_id else None
        try:
            required_by = datetime.fromisoformat(required_text)
        except ValueError:
            required_by = None
        if not medicine or quantity is None or quantity <= 0 or urgency not in URGENCY_LEVELS or not reason or not required_by:
            flash("Please enter valid request details. Quantity must be greater than zero.", "danger")
        else:
            med_request = MedicineRequest(
                requesting_facility_id=current_user.facility_id, medicine_id=medicine.id,
                quantity_requested=quantity, urgency=urgency, reason=reason,
                required_by=required_by, priority_score=calculate_priority(urgency, required_by)
            )
            db.session.add(med_request)
            db.session.commit()
            flash("Medicine request created. Available matching stock is shown below.", "success")
            return redirect(url_for("request_detail", request_id=med_request.id))
    catalogue = Medicine.query.order_by(Medicine.name.asc()).all()
    default_required = (datetime.utcnow() + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M")
    return render_template("request_new.html", medicines=catalogue, urgency_levels=URGENCY_LEVELS,
                           default_required=default_required)


@app.route("/requests/<int:request_id>")
@facility_user_required
def request_detail(request_id):
    med_request = db.get_or_404(MedicineRequest, request_id)
    is_requester = med_request.requesting_facility_id == current_user.facility_id
    is_supplier = Transfer.query.filter_by(request_id=med_request.id, supplier_facility_id=current_user.facility_id).first() is not None
    has_matching_stock = InventoryItem.query.filter_by(
        facility_id=current_user.facility_id, medicine_id=med_request.medicine_id,
        stock_condition="Usable"
    ).filter(InventoryItem.expiry_date >= date.today()).first() is not None
    if current_user.role != "admin" and not (is_requester or is_supplier or has_matching_stock):
        abort(403)
    matches = get_matches(med_request) if med_request.status in ["Open", "Partially Fulfilled"] else []
    offers = Transfer.query.filter_by(request_id=med_request.id).order_by(Transfer.created_at.desc()).all()
    return render_template("request_detail.html", med_request=med_request, matches=matches, offers=offers)


@app.route("/requests/<int:request_id>/offer/<int:item_id>", methods=["POST"])
@facility_user_required
def offer_stock(request_id, item_id):
    med_request = db.get_or_404(MedicineRequest, request_id)
    item = db.get_or_404(InventoryItem, item_id)
    if item.facility_id != current_user.facility_id:
        abort(403)
    if med_request.status not in ["Open", "Partially Fulfilled"]:
        flash("This request is no longer open for offers.", "warning")
        return redirect(url_for("inventory"))
    qty = request.form.get("quantity", type=int)
    if item.medicine_id != med_request.medicine_id or qty is None or qty <= 0 or qty > item.available_quantity:
        flash("Offer quantity is invalid or exceeds currently available stock.", "danger")
    elif item.facility_id == med_request.requesting_facility_id:
        flash("You cannot offer stock to your own facility.", "danger")
    else:
        transfer = Transfer(request_id=med_request.id, supplier_facility_id=item.facility_id,
                            inventory_item_id=item.id, quantity=qty, status="Offered")
        db.session.add(transfer)
        db.session.commit()
        flash("Supply offer sent to the requesting facility.", "success")
    return redirect(url_for("request_detail", request_id=med_request.id))


@app.route("/transfers/<int:transfer_id>/<action>", methods=["POST"])
@facility_user_required
def transfer_action(transfer_id, action):
    transfer = db.get_or_404(Transfer, transfer_id)
    med_request = transfer.medicine_request
    is_requester = med_request.requesting_facility_id == current_user.facility_id
    is_supplier = transfer.supplier_facility_id == current_user.facility_id
    item = transfer.inventory_item

    if action == "accept":
        if not is_requester or transfer.status != "Offered":
            abort(403)
        # Recheck available quantity at acceptance time to prevent stale offers.
        if item.available_quantity < transfer.quantity:
            transfer.status = "Rejected"
            db.session.commit()
            flash("The offer could not be accepted because the available quantity has changed.", "warning")
        else:
            item.reserved_quantity += transfer.quantity
            transfer.status = "Accepted"
            transfer.accepted_at = datetime.utcnow()
            db.session.commit()
            flash("Offer accepted and stock reserved for this transfer.", "success")
    elif action == "reject":
        if not is_requester or transfer.status != "Offered":
            abort(403)
        transfer.status = "Rejected"
        db.session.commit()
        flash("Supply offer declined.", "info")
    elif action == "dispatch":
        if not is_supplier or transfer.status != "Accepted":
            abort(403)
        if item.reserved_quantity < transfer.quantity or item.quantity_on_hand < transfer.quantity:
            flash("Stock reservation is inconsistent. Contact the administrator.", "danger")
        else:
            item.reserved_quantity -= transfer.quantity
            item.quantity_on_hand -= transfer.quantity
            item.updated_at = datetime.utcnow()
            transfer.status = "Dispatched"
            transfer.dispatched_at = datetime.utcnow()
            db.session.commit()
            flash("Transfer marked as dispatched. The requesting facility should confirm receipt.", "success")
    elif action == "receive":
        if not is_requester or transfer.status != "Dispatched":
            abort(403)
        transfer.status = "Received"
        transfer.received_at = datetime.utcnow()
        med_request.quantity_fulfilled += transfer.quantity
        if med_request.quantity_fulfilled >= med_request.quantity_requested:
            med_request.status = "Fulfilled"
        else:
            med_request.status = "Partially Fulfilled"
        db.session.commit()
        flash("Receipt confirmed and request fulfilment updated.", "success")
    elif action == "cancel":
        if not (is_supplier or is_requester) or transfer.status not in ["Offered", "Accepted"]:
            abort(403)
        if transfer.status == "Accepted":
            item.reserved_quantity = max(0, item.reserved_quantity - transfer.quantity)
        transfer.status = "Cancelled"
        db.session.commit()
        flash("Transfer cancelled.", "info")
    else:
        abort(400)
    return redirect(url_for("request_detail", request_id=med_request.id))


@app.route("/reports")
@facility_user_required
def reports():
    facility_id = current_user.facility_id
    total_items = InventoryItem.query.filter_by(facility_id=facility_id).count()
    low_stock = InventoryItem.query.filter_by(facility_id=facility_id, stock_condition="Usable").filter(
        InventoryItem.quantity_on_hand - InventoryItem.reserved_quantity <= 10,
        InventoryItem.expiry_date >= date.today()
    ).count()
    near_expiry = InventoryItem.query.filter_by(facility_id=facility_id, stock_condition="Usable").filter(
        InventoryItem.expiry_date >= date.today(),
        InventoryItem.expiry_date <= date.today() + timedelta(days=90)
    ).count()
    open_requests = MedicineRequest.query.filter_by(requesting_facility_id=facility_id).filter(
        MedicineRequest.status.in_(["Open", "Partially Fulfilled"])
    ).count()
    return render_template("reports.html", total_items=total_items, low_stock=low_stock,
                           near_expiry=near_expiry, open_requests=open_requests)


@app.route("/health")
def health():
    return {"status": "ok", "app": "MedRelay"}


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to access this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The page or record could not be found."), 404


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")

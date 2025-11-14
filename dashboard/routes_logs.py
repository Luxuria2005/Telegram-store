# dashboard/routes_logs.py - Activity Logging System Routes
from flask import render_template, request, jsonify, session, send_file
from datetime import datetime, timedelta
from . import dashboard_bp
from .utils import (
    login_required, admin_required, get_accessible_sidebar_items, ARABIC_TEXTS,
    generate_client_logs_excel, generate_staff_logs_excel, get_filters_description
)
from database import db
from config import CURRENCY

# Staff Activity Logs Route
@dashboard_bp.route('/staff-logs')
@login_required
@admin_required
def staff_logs_page():
    """Staff activity logs dashboard - Only for admin users"""
    try:
        # Get filter parameters
        user_id = request.args.get('user_id', type=int)
        action_type = request.args.get('action_type', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        page = request.args.get('page', 1, type=int)
        limit = 50
        offset = (page - 1) * limit
        
        # Get logs
        logs = db.get_staff_activity_logs(
            user_id=user_id,
            action_type=action_type if action_type else None,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            limit=limit,
            offset=offset
        )
        
        # Get statistics
        stats = db.get_staff_activity_stats(days=30)
        
        # Get all users for filter dropdown
        all_users = db.get_all_users()
        
        # Get unique action types for filter
        all_logs = db.get_staff_activity_logs(limit=1000)
        action_types = sorted(set(log.get('action_type', '') for log in all_logs if log.get('action_type')))
        
        # Get accessible sidebar items
        sidebar_items = get_accessible_sidebar_items()
        
        return render_template('staff_logs.html',
                             logs=logs,
                             stats=stats,
                             all_users=all_users,
                             action_types=action_types,
                             current_user_id=user_id,
                             current_action_type=action_type,
                             current_start_date=start_date,
                             current_end_date=end_date,
                             current_page=page,
                             sidebar_items=sidebar_items,
                             user_role=session.get('role'),
                             user_permissions=session.get('permissions', {}),
                             user_full_name=session.get('full_name'),
                             texts=ARABIC_TEXTS,
                             CURRENCY=CURRENCY)
        
    except Exception as e:
        print(f"❌ Error loading staff logs page: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Client Activity Logs Route
@dashboard_bp.route('/client-logs')
@login_required
@admin_required
def client_logs_page():
    """Client activity logs dashboard - Only for admin users"""
    try:
        # Get filter parameters
        telegram_id = request.args.get('telegram_id', type=int)
        activity_type = request.args.get('activity_type', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        page = request.args.get('page', 1, type=int)
        limit = 50
        offset = (page - 1) * limit
        
        # Get logs
        logs = db.get_client_activity_logs(
            telegram_id=telegram_id,
            activity_type=activity_type if activity_type else None,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            limit=limit,
            offset=offset
        )
        
        # Get statistics
        stats = db.get_client_activity_stats(days=30)
        
        # ✅ NEW: Get client interests if a specific client is selected
        client_interests = None
        if telegram_id:
            try:
                client_interests = db.get_client_interests(telegram_id, days=90)
            except Exception as e:
                print(f"⚠️ Error getting client interests: {e}")
                client_interests = None
        
        # Get all bot users for filter dropdown
        all_bot_users = db.get_all_bot_users()
        
        # Get unique activity types for filter
        all_logs = db.get_client_activity_logs(limit=1000)
        activity_types = sorted(set(log.get('activity_type', '') for log in all_logs if log.get('activity_type')))
        
        # Get accessible sidebar items
        sidebar_items = get_accessible_sidebar_items()
        
        return render_template('client_logs.html',
                             logs=logs,
                             stats=stats,
                             client_interests=client_interests,
                             all_bot_users=all_bot_users,
                             activity_types=activity_types,
                             current_telegram_id=telegram_id,
                             current_activity_type=activity_type,
                             current_start_date=start_date,
                             current_end_date=end_date,
                             current_page=page,
                             sidebar_items=sidebar_items,
                             user_role=session.get('role'),
                             user_permissions=session.get('permissions', {}),
                             user_full_name=session.get('full_name'),
                             texts=ARABIC_TEXTS,
                             CURRENCY=CURRENCY)
        
    except Exception as e:
        print(f"❌ Error loading client logs page: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ✅ NEW: Export Client Logs to Excel
@dashboard_bp.route('/export-client-logs')
@login_required
@admin_required
def export_client_logs():
    """Export client logs to Excel"""
    try:
        # Get the same filter parameters as the main page
        telegram_id = request.args.get('telegram_id', type=int)
        activity_type = request.args.get('activity_type', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        # Get all logs (no pagination for export)
        logs = db.get_client_activity_logs(
            telegram_id=telegram_id,
            activity_type=activity_type if activity_type else None,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            limit=10000,  # Large limit to get all records
            offset=0
        )
        
        # Generate filters description
        filters_desc = get_filters_description(request.args)
        
        # Generate Excel file
        excel_file = generate_client_logs_excel(logs, filters_desc)
        
        if excel_file:
            filename = f"client_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            return send_file(
                excel_file,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            return jsonify({"error": "Failed to generate Excel file"}), 500
            
    except Exception as e:
        print(f"❌ Error exporting client logs: {e}")
        return jsonify({"error": str(e)}), 500

# ✅ NEW: Export Staff Logs to Excel
@dashboard_bp.route('/export-staff-logs')
@login_required
@admin_required
def export_staff_logs():
    """Export staff logs to Excel"""
    try:
        # Get the same filter parameters as the main page
        user_id = request.args.get('user_id', type=int)
        action_type = request.args.get('action_type', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        # Get all logs (no pagination for export)
        logs = db.get_staff_activity_logs(
            user_id=user_id,
            action_type=action_type if action_type else None,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            limit=10000,  # Large limit to get all records
            offset=0
        )
        
        # Generate filters description
        filters_desc = get_filters_description(request.args)
        
        # Generate Excel file
        excel_file = generate_staff_logs_excel(logs, filters_desc)
        
        if excel_file:
            filename = f"staff_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            return send_file(
                excel_file,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            return jsonify({"error": "Failed to generate Excel file"}), 500
            
    except Exception as e:
        print(f"❌ Error exporting staff logs: {e}")
        return jsonify({"error": str(e)}), 500

# API Routes for getting logs (AJAX)
@dashboard_bp.route('/api/staff-logs')
@login_required
@admin_required
def api_get_staff_logs():
    """API endpoint to get staff logs (AJAX)"""
    try:
        user_id = request.args.get('user_id', type=int)
        action_type = request.args.get('action_type', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        page = request.args.get('page', 1, type=int)
        limit = 50
        offset = (page - 1) * limit
        
        logs = db.get_staff_activity_logs(
            user_id=user_id,
            action_type=action_type if action_type else None,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            limit=limit,
            offset=offset
        )
        
        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@dashboard_bp.route('/api/client-logs')
@login_required
@admin_required
def api_get_client_logs():
    """API endpoint to get client logs (AJAX)"""
    try:
        telegram_id = request.args.get('telegram_id', type=int)
        activity_type = request.args.get('activity_type', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        page = request.args.get('page', 1, type=int)
        limit = 50
        offset = (page - 1) * limit
        
        logs = db.get_client_activity_logs(
            telegram_id=telegram_id,
            activity_type=activity_type if activity_type else None,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            limit=limit,
            offset=offset
        )
        
        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
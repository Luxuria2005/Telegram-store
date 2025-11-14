// Enhanced Dashboard Functionality - SIMPLIFIED AND WORKING
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔄 Initializing enhanced dashboard...');

    // Update current time
    function updateTime() {
        const now = new Date();
        const timeString = now.toLocaleString('ar-EG', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        const timeElement = document.getElementById('current-time');
        if (timeElement) {
            timeElement.textContent = timeString;
        }
    }
    setInterval(updateTime, 60000);
    updateTime();

    // Mobile menu toggle
    const menuToggle = document.createElement('button');
    menuToggle.innerHTML = '<i class="fas fa-bars"></i>';
    menuToggle.className = 'mobile-menu-toggle';
    menuToggle.addEventListener('click', function() {
        document.querySelector('.sidebar').classList.toggle('active');
    });
    document.body.appendChild(menuToggle);

    // Show/hide mobile menu button based on screen size
    function checkScreenSize() {
        if (window.innerWidth < 992) {
            menuToggle.style.display = 'flex';
        } else {
            menuToggle.style.display = 'none';
            document.querySelector('.sidebar').classList.remove('active');
        }
    }
    
    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);

    // Image preview
    const productImage = document.getElementById('productImage');
    if (productImage) {
        productImage.addEventListener('change', function(e) {
            const file = e.target.files[0];
            const preview = document.getElementById('imagePreview');
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                }
                reader.readAsDataURL(file);
            }
        });
    }

    // Variant management
    let variantCounter = 0;

    window.addVariant = function() {
        const container = document.getElementById('variantsContainer');
        if (!container) return;

        const variantId = variantCounter++;
        
        const variantHtml = `
            <div class="variant-item" id="variant-${variantId}">
                <div class="row g-2 align-items-center">
                    <div class="col-md-3">
                        <label class="form-label">اللون</label>
                        <input type="text" class="form-control" name="color_${variantId}" placeholder="أحمر" required>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">المقاس</label>
                        <input type="text" class="form-control" name="size_${variantId}" placeholder="M" required>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">الكمية</label>
                        <input type="number" class="form-control" name="quantity_${variantId}" value="10" min="0" required>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">&nbsp;</label>
                        <div>
                            <button type="button" class="btn btn-danger btn-sm w-100" onclick="removeVariant(${variantId})">
                                <i class="fas fa-trash"></i> إزالة
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        container.insertAdjacentHTML('beforeend', variantHtml);
        document.getElementById('variantCount').value = variantCounter;
    }

    window.removeVariant = function(id) {
        const element = document.getElementById(`variant-${id}`);
        if (element) {
            element.remove();
        }
    }

    // Stock update function
    window.updateStock = function(category, productId, color, size, change) {
        const formData = new FormData();
        formData.append('category', category);
        formData.append('product_id', productId);
        formData.append('color', color);
        formData.append('size', size);
        formData.append('quantity_change', change);
        
        fetch('/update_inventory', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                location.reload();
            } else {
                alert('خطأ: ' + data.message);
            }
        })
        .catch(error => {
            alert('حدث خطأ في الاتصال');
        });
    }

    // ENHANCED Order status update for all_orders.html
    document.querySelectorAll('.update-status').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const status = this.dataset.status;
            const orderRow = this.closest('tr');
            const orderId = orderRow.querySelector('td:first-child strong').textContent.replace('#', '');
            const currentStatus = orderRow.querySelector('.status-badge').textContent.trim();
            
            // Prevent changing status from delivered
            if (currentStatus.includes('تم التوصيل') || currentStatus.includes('delivered')) {
                alert('❌ لا يمكن تغيير حالة الطلب بعد التوصيل');
                return false;
            }
            
            if (confirm('هل أنت متأكد من تغيير حالة الطلب؟')) {
                const formData = new FormData();
                formData.append('order_id', orderId);
                formData.append('status', status);
                
                fetch('/update_order_status', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(data.message);
                        location.reload();
                    } else {
                        alert('حدث خطأ: ' + data.message);
                    }
                })
                .catch(error => {
                    alert('حدث خطأ في الاتصال');
                });
            }
            
            return false;
        });
    });

    // ✅ FIXED: Enhanced order deletion with status validation
    document.querySelectorAll('.delete-order').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const orderId = this.getAttribute('data-order-id');
            const orderStatus = this.getAttribute('data-order-status') || '';
            const statusLower = orderStatus.toLowerCase();
            
            // Define deletable and non-deletable statuses
            const deletableStatuses = ['pending', 'confirmed', 'shipped', 'معلق', 'مؤكد', 'مشحون'];
            const nonDeletableStatuses = ['delivered', 'completed', 'تم التوصيل', 'مكتمل'];
            
            // Check if order can be deleted
            const canDelete = deletableStatuses.some(status => statusLower.includes(status));
            const cannotDelete = nonDeletableStatuses.some(status => statusLower.includes(status));
            
            if (cannotDelete) {
                alert(`❌ لا يمكن حذف الطلب #${orderId}\n\nالطلبات بحالة "${orderStatus}" لا يمكن حذفها لأنها مكتملة أو مسلمة.\n\nيمكنك فقط حذف الطلبات المعلقة أو المؤكدة أو المشحونة.`);
                return false;
            }
            
            if (!canDelete) {
                alert(`❌ لا يمكن حذف الطلب #${orderId}\n\nحالة الطلب "${orderStatus}" غير معروفة أو غير قابلة للحذف.`);
                return false;
            }
            
            // Show confirmation with inventory restoration info
            const confirmMessage = `🗑️ هل أنت متأكد من حذف الطلب #${orderId}؟\n\n⚠️ سيتم:\n• حذف الطلب بشكل دائم\n• استعادة الكميات إلى المخزون\n• لا يمكن التراجع عن هذا الإجراء`;
            
            if (confirm(confirmMessage)) {
                // Show loading state
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الحذف...';
                this.disabled = true;
                
                // Redirect to the delete route
                window.location.href = `/delete_order/${orderId}`;
            }
            
            return false;
        });
    });

    // Auto-refresh stats every 30 seconds
    setInterval(() => {
        fetch('/api/stats')
            .then(response => response.json())
            .then(stats => {
                const statNumbers = document.querySelectorAll('.stat-card .stat-number');
                if (statNumbers[0]) statNumbers[0].textContent = stats.total_orders;
                if (statNumbers[1]) statNumbers[1].textContent = stats.pending_orders;
                if (statNumbers[2]) statNumbers[2].textContent = stats.completed_orders;
                if (statNumbers[3]) statNumbers[3].textContent = stats.total_revenue;
            });
    }, 30000);

    // Add one variant by default
    if (document.getElementById('variantsContainer')) {
        addVariant();
    }

    console.log('✅ Enhanced dashboard initialized successfully');
});

// Global function for status updates (can be called from anywhere)
window.updateOrderStatusGlobal = function(orderId, status) {
    if (confirm('هل أنت متأكد من تغيير حالة الطلب؟')) {
        const formData = new FormData();
        formData.append('order_id', orderId);
        formData.append('status', status);
        
        fetch('/update_order_status', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                location.reload();
            } else {
                alert('حدث خطأ: ' + data.message);
            }
        })
        .catch(error => {
            alert('حدث خطأ في الاتصال');
        });
    }
};

// Enhanced dropdown positioning for all_orders.html
window.positionDropdown = function(menu, toggle) {
    const toggleRect = toggle.getBoundingClientRect();
    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;
    
    // Reset positioning
    menu.style.position = 'fixed';
    menu.style.top = 'auto';
    menu.style.bottom = 'auto';
    menu.style.left = 'auto';
    menu.style.right = 'auto';
    
    // Calculate position - position below the toggle button
    let top = toggleRect.bottom + window.scrollY;
    let left = toggleRect.left + window.scrollX;
    
    // Adjust for RTL - position to the left of toggle
    left = toggleRect.right + window.scrollX - menu.offsetWidth;
    
    // Check viewport boundaries
    if (left < 10) left = 10;
    if (left + menu.offsetWidth > viewportWidth) {
        left = viewportWidth - menu.offsetWidth - 10;
    }
    
    // Check if there's space below, otherwise position above
    if (top + menu.offsetHeight > viewportHeight + window.scrollY) {
        top = toggleRect.top + window.scrollY - menu.offsetHeight - 5;
    }
    
    // Ensure minimum spacing from top
    top = Math.max(10, top);
    
    // Apply positioning
    menu.style.top = top + 'px';
    menu.style.left = left + 'px';
    
    // Ensure dropdown is fully visible
    const menuRect = menu.getBoundingClientRect();
    if (menuRect.right > viewportWidth) {
        menu.style.left = (viewportWidth - menu.offsetWidth - 10) + 'px';
    }
    if (menuRect.bottom > viewportHeight) {
        menu.style.top = (viewportHeight - menu.offsetHeight - 10) + 'px';
    }
};

// Product Search Functionality
window.filterProducts = function() {
    const searchTerm = document.getElementById('productSearch').value.toLowerCase().trim();
    const productItems = document.querySelectorAll('.product-item');
    const categorySections = document.querySelectorAll('.category-section');
    const noResults = document.getElementById('noResults');
    
    let visibleProducts = 0;
    let visibleCategories = 0;

    // Show all if search is empty
    if (searchTerm === '') {
        productItems.forEach(item => {
            item.classList.remove('hidden');
            visibleProducts++;
        });
        
        categorySections.forEach(section => {
            const categoryProducts = section.querySelectorAll('.product-item');
            const visibleInCategory = Array.from(categoryProducts).filter(item => !item.classList.contains('hidden')).length;
            
            if (visibleInCategory > 0) {
                section.classList.remove('hidden');
                section.querySelector('.category-product-count').textContent = `${visibleInCategory} منتج`;
                visibleCategories++;
            } else {
                section.classList.add('hidden');
            }
        });
    } else {
        // Filter products based on search term
        productItems.forEach(item => {
            const productName = item.getAttribute('data-name');
            const modelNumber = item.getAttribute('data-model');
            const description = item.getAttribute('data-description');
            
            const matchesSearch = productName.includes(searchTerm) || 
                                 modelNumber.includes(searchTerm) || 
                                 description.includes(searchTerm);
            
            if (matchesSearch) {
                item.classList.remove('hidden');
                visibleProducts++;
            } else {
                item.classList.add('hidden');
            }
        });
        
        // Show/hide categories based on visible products
        categorySections.forEach(section => {
            const categoryProducts = section.querySelectorAll('.product-item');
            const visibleInCategory = Array.from(categoryProducts).filter(item => !item.classList.contains('hidden')).length;
            
            if (visibleInCategory > 0) {
                section.classList.remove('hidden');
                section.querySelector('.category-product-count').textContent = `${visibleInCategory} منتج`;
                visibleCategories++;
            } else {
                section.classList.add('hidden');
            }
        });
    }
    
    // Update search stats
    updateSearchStats(visibleProducts, visibleCategories);
    
    // Show/hide no results message
    if (visibleProducts === 0 && searchTerm !== '') {
        noResults.classList.remove('hidden');
        document.getElementById('productsContainer').classList.add('hidden');
    } else {
        noResults.classList.add('hidden');
        document.getElementById('productsContainer').classList.remove('hidden');
    }
};

window.updateSearchStats = function(visibleProducts, visibleCategories) {
    const searchStats = document.getElementById('searchStats');
    const searchTerm = document.getElementById('productSearch').value.trim();
    
    if (searchTerm === '') {
        searchStats.textContent = `عرض جميع المنتجات المتاحة`;
    } else {
        searchStats.textContent = `عرض ${visibleProducts} منتج في ${visibleCategories} فئة - نتائج البحث عن: "${searchTerm}"`;
    }
};

// Initialize search functionality
document.addEventListener('DOMContentLoaded', function() {
    // Focus search input on products page
    const productSearch = document.getElementById('productSearch');
    if (productSearch) {
        productSearch.focus();
        
        // Initialize search stats
        const productItems = document.querySelectorAll('.product-item:not(.hidden)');
        const categorySections = document.querySelectorAll('.category-section:not(.hidden)');
        updateSearchStats(productItems.length, categorySections.length);
    }
});
// ✅ NEW: Authentication and Session Management
// Session timeout warning
let sessionWarningShown = false;

function checkSessionTimeout() {
    // Check every minute
    setInterval(() => {
        fetch('/api/check_session')
            .then(response => response.json())
            .then(data => {
                if (!data.valid && !sessionWarningShown) {
                    sessionWarningShown = true;
                    showSessionWarning();
                }
            })
            .catch(error => {
                console.error('Session check failed:', error);
            });
    }, 60000);
}

function showSessionWarning() {
    const warningModal = `
        <div class="modal fade" id="sessionWarningModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-warning">
                        <h5 class="modal-title"><i class="fas fa-exclamation-triangle me-2"></i>تحذير انتهاء الجلسة</h5>
                    </div>
                    <div class="modal-body">
                        <p>جلسة العمل على وشك الانتهاء. سيتم تسجيل خروجك تلقائياً خلال دقائق قليلة.</p>
                        <p>هل تريد تمديد الجلسة؟</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="logout()">تسجيل الخروج</button>
                        <button type="button" class="btn btn-primary" onclick="extendSession()">تمديد الجلسة</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Add modal to body if not exists
    if (!document.getElementById('sessionWarningModal')) {
        document.body.insertAdjacentHTML('beforeend', warningModal);
    }
    
    const modal = new bootstrap.Modal(document.getElementById('sessionWarningModal'));
    modal.show();
}

function extendSession() {
    fetch('/api/extend_session', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                sessionWarningShown = false;
                const modal = bootstrap.Modal.getInstance(document.getElementById('sessionWarningModal'));
                modal.hide();
                
                // Show success message
                showToast('تم تمديد الجلسة بنجاح', 'success');
            }
        })
        .catch(error => {
            console.error('Failed to extend session:', error);
        });
}

function logout() {
    window.location.href = '/logout';
}

function showToast(message, type = 'info') {
    const toast = `
        <div class="toast align-items-center text-white bg-${type === 'success' ? 'success' : 'danger'} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    const toastContainer = document.getElementById('toastContainer') || createToastContainer();
    toastContainer.insertAdjacentHTML('beforeend', toast);
    
    const toastElement = toastContainer.lastElementChild;
    const bsToast = new bootstrap.Toast(toastElement);
    bsToast.show();
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

// ✅ NEW: Initialize authentication features
document.addEventListener('DOMContentLoaded', function() {
    // Initialize session timeout checking
    checkSessionTimeout();
    
    // Add user role badge to page title
    updatePageTitleWithRole();
    
    // Add inactivity detection
    setupInactivityDetection();
});

function updatePageTitleWithRole() {
    const userRole = document.querySelector('[data-user-role]')?.getAttribute('data-user-role');
    if (userRole) {
        const roleText = {
            'admin': 'مدير النظام',
            'order_manager': 'مدير الطلبات', 
            'user': 'مستخدم'
        }[userRole] || 'مستخدم';
        
        const currentTitle = document.title;
        if (!currentTitle.includes(roleText)) {
            document.title = `${currentTitle} - ${roleText}`;
        }
    }
}

function setupInactivityDetection() {
    let inactivityTime = 0;
    
    const resetInactivityTimer = () => {
        inactivityTime = 0;
    };
    
    // Reset timer on user activity
    ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'].forEach(event => {
        document.addEventListener(event, resetInactivityTimer, true);
    });
    
    // Check every minute
    setInterval(() => {
        inactivityTime += 1;
        
        // Warn after 25 minutes of inactivity (5 minutes before 30-minute timeout)
        if (inactivityTime === 25 && !sessionWarningShown) {
            showSessionWarning();
        }
    }, 60000);
}

// ✅ NEW: Permission-based UI controls
function checkPermission(permission) {
    // This would typically check against user permissions from the server
    // For now, we'll use data attributes on the body
    const userPermissions = document.body.getAttribute('data-user-permissions');
    return userPermissions ? userPermissions.includes(permission) : false;
}

// Disable unauthorized actions
function setupPermissionControls() {
    // Example: Hide delete buttons if user doesn't have permission
    if (!checkPermission('delete_orders')) {
        document.querySelectorAll('.delete-order').forEach(btn => {
            btn.style.display = 'none';
        });
    }
    
    // Example: Disable form submissions for unauthorized users
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredPermission = form.getAttribute('data-required-permission');
            if (requiredPermission && !checkPermission(requiredPermission)) {
                e.preventDefault();
                showToast('غير مصرح لك بتنفيذ هذا الإجراء', 'danger');
                return false;
            }
        });
    });
}

// Initialize permission controls when DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupPermissionControls);
} else {
    setupPermissionControls();
}
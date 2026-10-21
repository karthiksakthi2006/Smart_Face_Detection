/**
 * Smart Face Detection and Recognition System
 * Registered People Management (Cards/Table view, Instant Search, Deletion Modal)
 */

document.addEventListener('DOMContentLoaded', function () {
  const searchInput = document.getElementById('peopleSearchInput');
  const viewGridBtn = document.getElementById('viewGridBtn');
  const viewTableBtn = document.getElementById('viewTableBtn');
  const gridContainer = document.getElementById('peopleGridContainer');
  const tableContainer = document.getElementById('peopleTableContainer');
  const tableBody = document.getElementById('peopleTableBody');
  const emptyState = document.getElementById('peopleEmptyState');
  const totalCountBadge = document.getElementById('totalPeopleBadge');

  // Delete Modal elements
  const deleteModalEl = document.getElementById('deleteConfirmModal');
  const deleteModal = new bootstrap.Modal(deleteModalEl);
  const deletePersonNameEl = document.getElementById('deletePersonName');
  const deletePersonUidEl = document.getElementById('deletePersonUid');
  const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');

  let currentPeople = [];
  let personToDelete = null;
  let activeView = 'grid'; // 'grid' or 'table'

  // Load people from API
  async function loadPeople(query = '') {
    try {
      const url = query ? `/api/people?q=${encodeURIComponent(query)}` : '/api/people';
      const response = await fetch(url);
      const data = await response.json();

      if (data.success) {
        currentPeople = data.people || [];
        renderPeople(currentPeople);
        if (totalCountBadge) {
          totalCountBadge.textContent = `${currentPeople.length} Registered`;
        }
      } else {
        App.showToast('Failed to load registered people list.', 'error');
      }
    } catch (e) {
      console.error('Error fetching people:', e);
      App.showToast('Network error loading registered people.', 'error');
    }
  }

  // Render People in active view
  function renderPeople(people) {
    if (!people || people.length === 0) {
      gridContainer.innerHTML = '';
      tableBody.innerHTML = '';
      emptyState.style.display = 'block';
      return;
    }

    emptyState.style.display = 'none';

    // 1. Render Grid Cards
    gridContainer.innerHTML = '';
    people.forEach((p) => {
      const card = document.createElement('div');
      card.className = 'col-md-6 col-lg-4 col-xl-3';
      card.innerHTML = `
        <div class="person-card glass-card h-100">
          <div class="d-flex align-items-center gap-3">
            <img src="${p.thumbnail_path}" alt="${p.name}" class="person-thumbnail"
                 onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(p.name)}&background=0b1120&color=38bdf8';">
            <div style="flex: 1; overflow: hidden;">
              <h5 class="mb-1 text-truncate text-white" title="${p.name}">${p.name}</h5>
              <span class="badge-uid">${p.uid}</span>
            </div>
          </div>
          
          <div class="border-top border-secondary border-opacity-25 pt-2 mt-1 small text-muted">
            <div class="d-flex justify-content-between mb-1">
              <span>Registered:</span>
              <span class="text-white">${App.formatDate(p.created_at)}</span>
            </div>
            <div class="d-flex justify-content-between mb-1">
              <span>Recognitions:</span>
              <span class="badge-recognized">${p.recognition_count || 0} times</span>
            </div>
            <div class="d-flex justify-content-between">
              <span>Last Seen:</span>
              <span class="text-white">${p.last_seen_at ? App.formatDate(p.last_seen_at) : 'Never'}</span>
            </div>
          </div>

          <div class="mt-auto pt-2 d-flex gap-2">
            <button class="btn-modern-danger w-100 btn-sm delete-btn" data-id="${p.id}" data-uid="${p.uid}" data-name="${p.name}">
              <i class="bi bi-trash3"></i> Delete
            </button>
          </div>
        </div>
      `;
      gridContainer.appendChild(card);
    });

    // 2. Render Table Rows
    tableBody.innerHTML = '';
    people.forEach((p) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>
          <div class="d-flex align-items-center gap-3">
            <img src="${p.thumbnail_path}" alt="${p.name}" class="person-thumbnail"
                 onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(p.name)}&background=0b1120&color=38bdf8';">
            <div>
              <div class="fw-bold text-white">${p.name}</div>
              <small class="badge-uid">${p.uid}</small>
            </div>
          </div>
        </td>
        <td class="text-muted">${App.formatDate(p.created_at)}</td>
        <td>
          <span class="badge-recognized">${p.recognition_count || 0} detections</span>
        </td>
        <td class="text-muted">${p.last_seen_at ? App.formatDate(p.last_seen_at) : 'Never'}</td>
        <td class="text-end">
          <button class="btn-modern-danger btn-sm delete-btn" data-id="${p.id}" data-uid="${p.uid}" data-name="${p.name}">
            <i class="bi bi-trash3"></i> Delete
          </button>
        </td>
      `;
      tableBody.appendChild(tr);
    });

    // Attach delete handlers
    document.querySelectorAll('.delete-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const id = btn.getAttribute('data-id');
        const uid = btn.getAttribute('data-uid');
        const name = btn.getAttribute('data-name');
        openDeleteModal(id, uid, name);
      });
    });
  }

  // Switch Views
  if (viewGridBtn && viewTableBtn) {
    viewGridBtn.addEventListener('click', () => {
      activeView = 'grid';
      viewGridBtn.classList.add('active');
      viewTableBtn.classList.remove('active');
      gridContainer.style.display = 'flex';
      tableContainer.style.display = 'none';
    });

    viewTableBtn.addEventListener('click', () => {
      activeView = 'table';
      viewTableBtn.classList.add('active');
      viewGridBtn.classList.remove('active');
      gridContainer.style.display = 'none';
      tableContainer.style.display = 'block';
    });
  }

  // Live Search Input with debounce
  let searchTimeout = null;
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      const q = e.target.value.trim();
      searchTimeout = setTimeout(() => {
        loadPeople(q);
      }, 250);
    });
  }

  // Open Delete Confirmation Modal
  function openDeleteModal(id, uid, name) {
    personToDelete = { id, uid, name };
    deletePersonNameEl.textContent = name;
    deletePersonUidEl.textContent = uid;
    deleteModal.show();
  }

  // Execute Deletion
  confirmDeleteBtn.addEventListener('click', async () => {
    if (!personToDelete) return;

    confirmDeleteBtn.disabled = true;
    confirmDeleteBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Deleting...';

    try {
      const response = await fetch(`/api/people/${personToDelete.id}`, {
        method: 'DELETE'
      });
      const data = await response.json();

      if (data.success) {
        App.showToast(`Deleted ${personToDelete.name} and associated facial records.`, 'success', 'Record Removed');
        deleteModal.hide();
        // Reload list
        loadPeople(searchInput ? searchInput.value.trim() : '');
      } else {
        App.showToast(data.error || 'Failed to delete record.', 'error');
      }
    } catch (e) {
      console.error('Delete error:', e);
      App.showToast('Network error while deleting.', 'error');
    } finally {
      confirmDeleteBtn.disabled = false;
      confirmDeleteBtn.innerHTML = '<i class="bi bi-trash3 me-1"></i> Delete Person Permanently';
      personToDelete = null;
    }
  });

  // Initial load
  loadPeople();
});

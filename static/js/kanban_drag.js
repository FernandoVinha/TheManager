document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("kanbanRoot");
  if (!root) return;

  const projectId = root.dataset.projectId;
  let dragged = null;

  // =============== DRAG START / END ===============
  function attachCardEvents(card) {
    card.addEventListener("dragstart", (e) => {
      dragged = card;
      card.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
    });

    card.addEventListener("dragend", () => {
      if (dragged) {
        dragged.classList.remove("dragging");
        dragged = null;
      }
    });
  }

  document.querySelectorAll(".task-card").forEach(attachCardEvents);

  // =============== DROP ZONES (COLUMNS) ===============
  document.querySelectorAll(".kanban-dropzone").forEach((zone) => {
    zone.addEventListener("dragover", (e) => {
      e.preventDefault();
      zone.classList.add("drag-over");
      e.dataTransfer.dropEffect = "move";
    });

    zone.addEventListener("dragleave", (e) => {
      if (!zone.contains(e.relatedTarget)) {
        zone.classList.remove("drag-over");
      }
    });

    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("drag-over");
      if (!dragged) return;

      const taskId = dragged.dataset.taskId;
      const newStatus = zone.closest(".kanban-column").dataset.status;

      // move visualmente
      zone.appendChild(dragged);

      // remove "Empty" se existir
      const emptyMsg = zone.querySelector(".empty-msg");
      if (emptyMsg) {
        emptyMsg.remove();
      }

      // atualiza no backend
      updateTaskStatus(projectId, taskId, newStatus);
    });
  });
});

// =============== AJAX REQUEST ===============
function updateTaskStatus(projectId, taskId, status) {
  const url = `/projects/${projectId}/kanban/status/${taskId}/`;

  const body = new URLSearchParams();
  body.append("status", status);

  fetch(url, {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: body.toString(),
  })
    .then((r) => {
      if (!r.ok) {
        throw new Error("HTTP " + r.status);
      }
      return r.json();
    })
    .then((data) => {
      if (!data.ok) {
        console.error("Error from server:", data);
        alert("Failed to update task: " + (data.error || "unknown error"));
      }
    })
    .catch((err) => {
      console.error(err);
      alert("Failed to update task status.");
    });
}

// =============== CSRF helper ===============
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

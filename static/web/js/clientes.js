document.addEventListener("DOMContentLoaded", function () {
  const clientsContainer = document.getElementById("clients-container");

  if (clientsContainer) {
      const cards = clientsContainer.children.length;

      if (cards > 10) {
          clientsContainer.classList.add("max-h-96", "overflow-y-auto");
      }
  }
});

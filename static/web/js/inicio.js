document.addEventListener("DOMContentLoaded", function () {
    let currentIndex = 0;
const carouselItems = document.querySelectorAll(".carousel-item");
const totalItems = carouselItems.length;

if (totalItems > 0) {
    carouselItems[currentIndex].classList.add("active");

    function changeImage() {
        carouselItems[currentIndex].classList.remove("active");
        carouselItems[currentIndex].classList.add("hidden");

        currentIndex = (currentIndex + 1) % totalItems;

        carouselItems[currentIndex].classList.remove("hidden");
        carouselItems[currentIndex].classList.add("active");
    }

    setInterval(changeImage, 5000);
}
});

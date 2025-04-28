// scripts.js

document.addEventListener('DOMContentLoaded', function() {
    const closeButtons = document.querySelectorAll('.close-btn');

    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const alertBox = this.parentElement;
            alertBox.style.display = 'none'; // Hide the flash message
        });
    });
});


// JavaScript for Carousel 
let slideIndex = 0;
showSlides(slideIndex);

function nextSlide() {
    showSlides(slideIndex += 1);
}

function prevSlide() {
    showSlides(slideIndex -= 1);
}

function showSlides(n) {
    let slides = document.getElementsByClassName("slide");

    if (n >= slides.length) { slideIndex = 0; } 
    if (n < 0) { slideIndex = slides.length - 1; }

    for (let i = 0; i < slides.length; i++) {
        slides[i].style.display = "none";
    }
    slides[slideIndex].style.display = "block";
}
//faq toogle
function toggleAnswer(questionElement) {
    const answerElement = questionElement.nextElementSibling;
    const toggleIcon = questionElement.querySelector('.toggle-icon');
    
    if (answerElement.style.display === "none" || answerElement.style.display === "") {
        answerElement.style.display = "block"; // Show the answer
        toggleIcon.textContent = "▲"; // Change icon to up arrow
        questionElement.classList.add('active'); // Add active class
    } else {
        answerElement.style.display = "none"; // Hide the answer
        toggleIcon.textContent = "▼"; // Change icon to down arrow
        questionElement.classList.remove('active'); // Remove active class
    }
}


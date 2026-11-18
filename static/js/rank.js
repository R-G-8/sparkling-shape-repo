// Ranking screen: swipe (phones) and arrow keys (desktop) pick a title.
// Without JavaScript the two buttons still work as plain form posts.
(function () {
  "use strict";
  var pair = document.getElementById("pair");
  if (!pair) return;
  var forms = {
    left: pair.querySelector('form[data-side="left"]'),
    right: pair.querySelector('form[data-side="right"]'),
  };
  var submitted = false;

  function pick(side) {
    var form = forms[side];
    if (!form || submitted) return;
    submitted = true;
    form.classList.add("picked");
    form.submit();
  }

  // Swipe toward the title you liked more: left picks the left card, right the right.
  var startX = null, startY = null;
  var MIN_SWIPE = 60;
  pair.addEventListener("touchstart", function (event) {
    if (event.touches.length !== 1) return;
    startX = event.touches[0].clientX;
    startY = event.touches[0].clientY;
  }, { passive: true });
  pair.addEventListener("touchend", function (event) {
    if (startX === null) return;
    var dx = event.changedTouches[0].clientX - startX;
    var dy = event.changedTouches[0].clientY - startY;
    startX = startY = null;
    if (Math.abs(dx) >= MIN_SWIPE && Math.abs(dx) > Math.abs(dy) * 1.5) {
      event.preventDefault(); // don't also treat the swipe as a tap
      pick(dx < 0 ? "left" : "right");
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === "ArrowLeft") pick("left");
    if (event.key === "ArrowRight") pick("right");
  });
})();

const menu = document.querySelector(".menu-button");
const nav = document.querySelector("#site-nav");
const setMenu = (open) => {
  menu.setAttribute("aria-expanded", String(open));
  nav.classList.toggle("open", open);
  document.body.style.overflow = open ? "hidden" : "";
};
menu.addEventListener("click", () =>
  setMenu(menu.getAttribute("aria-expanded") !== "true"),
);
nav.addEventListener("click", (event) => {
  if (event.target.closest("a")) setMenu(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && menu.getAttribute("aria-expanded") === "true") {
    setMenu(false);
    menu.focus();
  }
  if (event.key === "Tab" && menu.getAttribute("aria-expanded") === "true") {
    const controls = [menu, ...nav.querySelectorAll("a")];
    if (!event.shiftKey && document.activeElement === controls.at(-1)) {
      event.preventDefault();
      menu.focus();
    } else if (event.shiftKey && document.activeElement === menu) {
      event.preventDefault();
      controls.at(-1).focus();
    }
  }
});
matchMedia("(min-width: 601px)").addEventListener("change", (event) => {
  if (event.matches) setMenu(false);
});
const dialog = document.querySelector(".image-dialog");
document
  .querySelector(".screenshot-button")
  .addEventListener("click", () => dialog.showModal());
document
  .querySelector(".dialog-close")
  .addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});
const links = [...nav.querySelectorAll('a[href^="#"]')];
const observer = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      for (const link of links) {
        if (link.hash === `#${entry.target.id}`)
          link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      }
    }
  },
  { rootMargin: "-15% 0px -55% 0px" },
);
for (const link of links) {
  const section = document.querySelector(link.hash);
  if (section) observer.observe(section);
}

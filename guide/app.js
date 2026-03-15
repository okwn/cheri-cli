const sections = Array.from(document.querySelectorAll("[data-doc-section]"));
const navList = document.getElementById("nav-list");
const searchInput = document.getElementById("doc-search");
const searchMeta = document.getElementById("search-meta");

function buildNav() {
  navList.innerHTML = "";
  sections.forEach((section, index) => {
    const title = section.dataset.title || section.querySelector("h2, h1")?.textContent?.trim() || `Section ${index + 1}`;
    const item = document.createElement("li");
    const link = document.createElement("a");
    const label = document.createElement("span");
    const number = document.createElement("span");

    link.href = `#${section.id}`;
    link.dataset.sectionId = section.id;
    label.textContent = title;
    number.textContent = String(index + 1).padStart(2, "0");
    number.className = "nav-index";

    link.append(label, number);
    item.append(link);
    navList.append(item);
  });
}

function updateSearch(query) {
  const normalizedQuery = query.trim().toLowerCase();
  let matchCount = 0;

  sections.forEach((section) => {
    const haystack = [
      section.dataset.title || "",
      section.textContent || "",
      section.id || "",
    ].join(" ").toLowerCase();
    const matched = normalizedQuery === "" || haystack.includes(normalizedQuery);
    section.classList.toggle("is-hidden", !matched);
    if (matched) {
      matchCount += 1;
    }

    const navLink = navList.querySelector(`[data-section-id="${section.id}"]`);
    if (navLink) {
      navLink.parentElement.hidden = !matched;
    }
  });

  searchMeta.textContent = normalizedQuery ? `${matchCount} matching section${matchCount === 1 ? "" : "s"}` : `${sections.length} sections`;
}

function setActiveSection(id) {
  navList.querySelectorAll("a").forEach((link) => {
    link.classList.toggle("active", link.dataset.sectionId === id);
  });
}

function installAnchors() {
  sections.forEach((section) => {
    const button = section.querySelector(".anchor-button");
    if (!button) {
      return;
    }
    button.addEventListener("click", async () => {
      const hash = `#${section.id}`;
      const url = `${window.location.origin}${window.location.pathname}${hash}`;
      history.replaceState(null, "", hash);
      try {
        await navigator.clipboard.writeText(url);
        button.title = "Link copied";
      } catch {
        button.title = "Anchor ready";
      }
      section.classList.add("section-match");
      window.setTimeout(() => section.classList.remove("section-match"), 520);
    });
  });
}

function installObserver() {
  const observer = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
    if (visible) {
      setActiveSection(visible.target.id);
    }
  }, {
    rootMargin: "-18% 0px -62% 0px",
    threshold: [0.1, 0.35, 0.55],
  });

  sections.forEach((section) => observer.observe(section));
}

function visibleSections() {
  return sections.filter((section) => !section.classList.contains("is-hidden"));
}

function jumpSection(direction) {
  const visible = visibleSections();
  if (!visible.length) {
    return;
  }
  const currentHash = window.location.hash.replace("#", "");
  const currentIndex = Math.max(0, visible.findIndex((section) => section.id === currentHash));
  const nextIndex = Math.min(visible.length - 1, Math.max(0, currentIndex + direction));
  const target = visible[nextIndex];
  target.scrollIntoView({ behavior: "smooth", block: "start" });
  history.replaceState(null, "", `#${target.id}`);
  setActiveSection(target.id);
}

function installKeyboard() {
  window.addEventListener("keydown", (event) => {
    const tagName = document.activeElement?.tagName?.toLowerCase();
    const editing = tagName === "input" || tagName === "textarea";

    if (event.key === "/" && !editing) {
      event.preventDefault();
      searchInput.focus();
      searchInput.select();
      return;
    }

    if (event.key === "Escape" && document.activeElement === searchInput) {
      searchInput.value = "";
      updateSearch("");
      searchInput.blur();
      return;
    }

    if (editing) {
      return;
    }

    if (event.key.toLowerCase() === "j") {
      event.preventDefault();
      jumpSection(1);
    }

    if (event.key.toLowerCase() === "k") {
      event.preventDefault();
      jumpSection(-1);
    }
  });
}

function installSearch() {
  searchInput.addEventListener("input", (event) => {
    updateSearch(event.target.value);
  });
}

buildNav();
installAnchors();
installObserver();
installKeyboard();
installSearch();
updateSearch("");

if (window.location.hash) {
  const target = document.querySelector(window.location.hash);
  if (target) {
    target.classList.add("section-match");
    window.setTimeout(() => target.classList.remove("section-match"), 520);
  }
}

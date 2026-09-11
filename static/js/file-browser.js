document.addEventListener('DOMContentLoaded', () => {
  const navLinks = document.querySelectorAll('.nav-link');
  const mainContent = document.getElementById('main-content');

  const activeClasses = ['bg-stone-200', 'dark:bg-stone-800', 'text-stone-900', 'dark:text-stone-50'];
  const inactiveClasses = ['text-stone-600', 'dark:text-stone-400', 'hover:bg-stone-100', 'dark:hover:bg-stone-900', 'hover:text-stone-900', 'dark:hover:text-stone-50'];

  const icons = {
    image: `<svg class="w-12 h-12 text-stone-300 dark:text-stone-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>`,
    video: `<svg class="w-12 h-12 text-stone-300 dark:text-stone-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>`,
    document: `<svg class="w-14 h-14 drop-shadow-sm" viewBox="0 0 24 24" fill="none">
      <path d="M6 2.5h7.5L19 8v12.5a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 015 20.5v-16A1.5 1.5 0 016 2.5z" fill="#EEF2F7" stroke="#CBD5E1" stroke-width="1"/>
      <path d="M13.5 2.5V7a1 1 0 001 1H19" fill="none" stroke="#CBD5E1" stroke-width="1"/>
      <rect x="7.5" y="11.5" width="9" height="1.3" rx="0.65" fill="#93A5BC"/>
      <rect x="7.5" y="14.3" width="9" height="1.3" rx="0.65" fill="#93A5BC"/>
      <rect x="7.5" y="17.1" width="5.5" height="1.3" rx="0.65" fill="#93A5BC"/>
    </svg>`,
    audio: `<svg class="w-12 h-12 text-purple-500/80" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"></path></svg>`,
    folder: `<svg class="w-14 h-14 drop-shadow-sm" viewBox="0 0 24 24" fill="none">
      <path d="M2.5 6.5A1.5 1.5 0 014 5h5.17a1.5 1.5 0 011.06.44l1 1A1.5 1.5 0 0012.3 7H20a1.5 1.5 0 011.5 1.5V8h-19V6.5z" fill="#F3B94D"/>
      <path d="M1.5 8.25A1.25 1.25 0 012.75 7h18.5a1.25 1.25 0 011.25 1.25v10A2.75 2.75 0 0119.75 21H4.25a2.75 2.75 0 01-2.75-2.75v-10z" fill="#FBC24B"/>
      <path d="M1.5 8.25A1.25 1.25 0 012.75 7h18.5a1.25 1.25 0 011.25 1.25v1.5h-22v-1.5z" fill="#FFDE99"/>
    </svg>`
  };

  const apiData = {
    all: [
      { name: 'Documents', type: 'folder', date: 'Today', section: 'documents' },
      { name: 'Photos', type: 'folder', date: 'Today', section: 'images' },
      { name: 'Videos', type: 'folder', date: 'Today', section: 'videos' },
      { name: 'Music', type: 'folder', date: 'Today', section: 'music' },
      { name: 'Project', type: 'folder', date: 'Today' }
    ],
    images: [
      { name: 'IMG_20231024.jpg', type: 'image', date: 'Today' },
      { name: 'vacation.png', type: 'image', date: 'Last Week' }
    ],
    videos: [
      { name: 'VID_20231024.mp4', type: 'video', date: 'Today' },
      { name: 'screen_recording.mov', type: 'video', date: 'Last Month' }
    ],
    music: [
      { name: 'Audio Track 1.mp3', type: 'audio', date: 'Yesterday' },
      { name: 'podcast.m4a', type: 'audio', date: 'Last Month' }
    ],
    documents: [
      { name: 'Project Proposal.pdf', type: 'document', date: 'Yesterday' },
      { name: 'invoice.docx', type: 'document', date: 'Last Week' }
    ]
  };

  const sectionTitles = {
    all: 'Preview Design',
    images: 'Images',
    videos: 'Videos',
    music: 'Music',
    documents: 'Documents'
  };

  function renderHeader(title, showNewFolder) {
    const newFolderButton = showNewFolder ? `
          <button id="new-folder-btn" class="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold text-stone-700 dark:text-stone-200 bg-stone-100 hover:bg-stone-200 dark:bg-stone-900 dark:hover:bg-stone-800 rounded-lg border border-stone-300 dark:border-stone-700 transition-colors">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 13h6m-3-3v6M3 7a2 2 0 012-2h4l2 2h6a2 2 0 012 2v7a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"></path></svg>
            New Folder
          </button>` : '';
    return `
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-display font-semibold text-stone-900 dark:text-stone-50">${title}</h2>
        <div class="flex items-center gap-3">
          <button class="p-2 text-stone-500 hover:text-stone-900 dark:text-stone-400 dark:hover:text-stone-50 bg-stone-100 hover:bg-stone-200 dark:bg-stone-900 dark:hover:bg-stone-800 rounded-lg transition-colors">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>
          </button>${newFolderButton}
          <button class="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-amber-700 rounded-lg hover:bg-amber-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-amber-700 dark:focus-visible:ring-offset-stone-950 transition-colors shadow-sm">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path></svg>
            Upload
          </button>
        </div>
      </div>
    `;
  }

  function renderCard(item) {
    if (item.type === 'folder') {
      const goto = item.section ? ` data-goto-section="${item.section}"` : '';
      return `
        <div class="flex flex-col items-center justify-center gap-2 p-3 rounded-xl cursor-pointer hover:bg-stone-200/60 dark:hover:bg-stone-800/60 transition-colors"${goto}>
          ${icons.folder}
          <p class="text-stone-700 dark:text-stone-200 text-xs font-medium px-1 text-center truncate w-full">${item.name}</p>
        </div>
      `;
    }
    return `
      <div class="group relative aspect-square bg-stone-100 dark:bg-stone-900 rounded-xl overflow-hidden border border-stone-200 dark:border-stone-800 cursor-pointer hover:border-amber-500 dark:hover:border-amber-600 transition-all">
        <div class="absolute inset-0 flex items-center justify-center">
          ${icons[item.type]}
        </div>
        <div class="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
          <p class="text-white text-xs font-medium truncate">${item.name}</p>
        </div>
      </div>
    `;
  }

  function renderContent(section) {
    const data = apiData[section] || [];
    const title = sectionTitles[section] || 'Files';

    const grouped = data.reduce((acc, item) => {
      if (!acc[item.date]) acc[item.date] = [];
      acc[item.date].push(item);
      return acc;
    }, {});

    const showNewFolder = section === 'all';
    let html = renderHeader(title, showNewFolder);

    if (Object.keys(grouped).length === 0) {
       html += `<div class="text-stone-500 dark:text-stone-400 mt-8">No files found.</div>`;
       mainContent.innerHTML = html;
       bindNewFolderButton(showNewFolder);
       return;
    }

    for (const [date, items] of Object.entries(grouped)) {
      html += `
        <div class="mb-8 fade-in">
          <h3 class="text-sm font-medium text-stone-500 dark:text-stone-400 mb-4 uppercase tracking-wider">${date}</h3>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            ${items.map(item => renderCard(item)).join('')}
          </div>
        </div>
      `;
    }

    mainContent.innerHTML = html;
    bindNewFolderButton(showNewFolder);
  }

  function bindNewFolderButton(enabled) {
    if (!enabled) return;
    const btn = document.getElementById('new-folder-btn');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const name = window.prompt('Folder name');
      if (!name || !name.trim()) return;
      apiData.all.unshift({ name: name.trim(), type: 'folder', date: 'Today' });
      renderContent('all');
    });
  }

  function setSection(sectionName) {
    navLinks.forEach(link => {
      const isMatch = link.dataset.section === sectionName;
      const svg = link.querySelector('svg');

      if (isMatch) {
        link.classList.remove(...inactiveClasses);
        link.classList.add(...activeClasses);
        svg.classList.remove('text-stone-600', 'dark:text-stone-400');
        svg.classList.add('text-stone-600', 'dark:text-stone-300');
      } else {
        link.classList.remove(...activeClasses);
        link.classList.add(...inactiveClasses);
        svg.classList.remove('text-stone-600', 'dark:text-stone-300');
      }
    });

    mainContent.innerHTML = `
      <div class="flex items-center justify-center h-64">
        <svg class="w-8 h-8 text-amber-600 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </div>
    `;

    setTimeout(() => {
      renderContent(sectionName);
    }, 400);
  }

  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const section = link.dataset.section;
      history.pushState(null, '', `#${section}`);
      setSection(section);
    });
  });

  // Folder cards that link to a sidebar section (delegated, since cards are re-rendered)
  mainContent.addEventListener('click', (e) => {
    const target = e.target.closest('[data-goto-section]');
    if (!target) return;
    const section = target.dataset.gotoSection;
    history.pushState(null, '', `#${section}`);
    setSection(section);
  });

  window.addEventListener('popstate', () => {
    const hash = window.location.hash.slice(1) || 'all';
    setSection(hash);
  });

  const initialSection = window.location.hash.slice(1) || 'all';
  setSection(initialSection);
});

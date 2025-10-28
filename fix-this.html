<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>李奇安九沐方舟</title>
<style>
    * { margin:0; padding:0; box-sizing:border-box; font-family:'Segoe UI', sans-serif; }
    body { background:#f9f9f9; color:#333; }
    nav { background:#222; color:#fff; display:flex; justify-content:space-between; align-items:center; padding:0.5rem 2rem; position:sticky; top:0; z-index:100; }
    nav .logo { font-size:1.5rem; font-weight:bold; }
    nav .links { display:flex; gap:1rem; }
    nav .links a { color:#fff; text-decoration:none; cursor:pointer; }
    nav .links a:hover { color:#f0a500; }
    .hero { width:100%; height:70vh; overflow:hidden; position:relative; }
    .hero img { width:100%; height:100%; object-fit:cover; filter:brightness(0.85); }
    .hero .title { position:absolute; bottom:2rem; left:2rem; color:#fff; font-size:3rem; font-weight:bold; text-shadow:2px 2px 8px rgba(0,0,0,0.7); }
    .search-bar { margin:2rem auto; max-width:600px; display:flex; }
    .search-bar input { flex:1; padding:0.5rem 1rem; font-size:1rem; border:2px solid #ddd; border-radius:4px 0 0 4px; }
    .search-bar button { padding:0.5rem 1rem; border:none; background:#f0a500; color:#fff; cursor:pointer; border-radius:0 4px 4px 0; }
    .search-bar button:hover { background:#d18e00; }
    .gallery { display:grid; grid-template-columns:repeat(auto-fit, minmax(250px,1fr)); gap:1.5rem; padding:2rem; }
    .card { background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 4px 12px rgba(0,0,0,0.1); cursor:pointer; transition:transform 0.2s; }
    .card:hover { transform:translateY(-5px); }
    .card img { width:100%; height:250px; object-fit:cover; }
    .card .card-title { padding:0.5rem 1rem; font-weight:bold; text-align:center; }
    .modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); justify-content:center; align-items:center; z-index:200; }
    .modal-content { background:#fff; padding:2rem; border-radius:8px; max-width:90%; max-height:90%; overflow:auto; position:relative; }
    .modal-content img { width:100%; max-height:400px; object-fit:contain; }
    .modal-content .description { margin-top:1rem; font-size:1rem; line-height:1.5; }
    .modal-close { position:absolute; top:1rem; right:1rem; font-size:1.5rem; cursor:pointer; }
    footer { text-align:center; padding:1rem; background:#222; color:#fff; margin-top:2rem; }
    .tooltip { position:relative; display:inline-block; }
    .tooltip .tooltiptext { visibility:hidden; width:120px; background:#333; color:#fff; text-align:center; padding:5px 0; border-radius:6px; position:absolute; z-index:1; bottom:125%; left:50%; margin-left:-60px; opacity:0; transition:opacity 0.3s; }
    .tooltip:hover .tooltiptext { visibility:visible; opacity:1; }
</style>
</head>
<body>

<nav>
    <div class="logo">李奇安九沐方舟</div>
    <div class="links">
        <a href="#gallery">画廊</a>
        <a class="tooltip" onclick="copyWeChat()">联系
            <span class="tooltiptext">点击复制微信</span>
        </a>
    </div>
</nav>

<section class="hero">
    <img id="heroImage" src="" alt="李奇安">
    <div class="title">李奇安</div>
</section>

<div class="search-bar">
    <input type="text" id="searchInput" placeholder="搜索画作...">
    <button onclick="searchGallery()">搜索</button>
</div>

<section class="gallery" id="gallery"></section>

<div class="modal" id="modal">
    <div class="modal-content">
        <span class="modal-close" onclick="closeModal()">&times;</span>
        <img id="modalImage" src="" alt="">
        <div class="description" id="modalDescription"></div>
    </div>
</div>

<footer>
    © 2025 李奇安九沐方舟
</footer>

<script>
const githubRepoOwner = "📁你的GitHub用户名"; // replace with your GitHub username
const githubRepoName = "📁你的Repo名"; // replace with your repo name
const githubBranch = "main"; // usually main or master

let paintings = [];
const gallery = document.getElementById('gallery');
const heroImage = document.getElementById('heroImage');

// Fetch repo contents
async function fetchRepo(){
    const apiUrl = `https://api.github.com/repos/${githubRepoOwner}/${githubRepoName}/contents/`;
    const res = await fetch(apiUrl);
    const files = await res.json();

    let heroSet = false;

    for(const file of files){
        const ext = file.name.split('.').pop().toLowerCase();
        if(['jpg','jpeg','png','webp'].includes(ext)){
            if(file.name.toLowerCase().includes('liqian') && !heroSet){
                heroImage.src = file.download_url;
                heroSet = true;
            }
            paintings.push({title:file.name.split('.').slice(0,-1).join(' '), file:file.name});
        }
    }

    renderGallery(paintings);
}

// Render gallery
function renderGallery(list){
    gallery.innerHTML = '';
    list.forEach(p=>{
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <img src="https://raw.githubusercontent.com/${githubRepoOwner}/${githubRepoName}/${githubBranch}/${p.file}" alt="${p.title}">
            <div class="card-title">${p.title}</div>
        `;
        card.onclick = ()=>openModal(p);
        gallery.appendChild(card);
    });
}

// Modal
const modal = document.getElementById('modal');
const modalImage = document.getElementById('modalImage');
const modalDescription = document.getElementById('modalDescription');

async function openModal(p){
    modal.style.display = 'flex';
    modalImage.src = `https://raw.githubusercontent.com/${githubRepoOwner}/${githubRepoName}/${githubBranch}/${p.file}`;
    const descFile = p.file.split('.').slice(0,-1).join('.')+'.txt';
    try{
        const res = await fetch(`https://raw.githubusercontent.com/${githubRepoOwner}/${githubRepoName}/${githubBranch}/${descFile}`);
        if(res.ok){
            modalDescription.textContent = await res.text();
        } else {
            modalDescription.textContent = "没有描述。";
        }
    }catch{
        modalDescription.textContent = "没有描述。";
    }
}

function closeModal(){ modal.style.display = 'none'; }

// Search
function searchGallery(){
    const keyword = document.getElementById('searchInput').value.trim();
    if(!keyword) return renderGallery(paintings);
    const filtered = paintings.filter(p=>p.title.includes(keyword));
    renderGallery(filtered);
}

// Copy WeChat
function copyWeChat(){
    navigator.clipboard.writeText("VibeOil777").then(()=>{ alert("微信号已复制: VibeOil777 😎"); });
}

fetchRepo();
</script>
</body>
</html>

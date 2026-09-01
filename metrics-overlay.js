(function(){
  function fmt(v){ return Number(v||0).toLocaleString('ru-RU'); }
  function mln(v){ return (Number(v||0)/1e6).toFixed(2); }
  function esc(s){ return String(s).replace(/[&<>\"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c];}); }
  function pill(p){
    if(p==null) return '<span class="muted">—</span>';
    return '<span class="pill '+(p>=100?'good':(p>=70?'warn':'bad'))+'">'+p+'%</span>';
  }
  function delta(d){
    if(d==null) return '<span class="muted">—</span>';
    var up=d>=0;
    return '<span class="delta '+(up?'up':'down')+'">'+(up?'▲':'▼')+' '+Math.abs(d).toFixed(1)+'%</span>';
  }
  function enhance(){
    var D=window.DASH_DATA, table=document.getElementById('deptTable');
    if(!D||!table||table.querySelector('thead th:nth-child(2)')?.textContent.indexOf('Клиенты')>=0) return;
    var colors={'ТЗ':'var(--blue)','ГП':'var(--indigo)','БК':'var(--purple)','ДЦ':'var(--yellow)','Мероприятия ФД':'var(--teal)','Массаж':'var(--orange)','СМ':'var(--magenta)'};
    var rows=D.departments.map(function(d){return '<tr>'+
      '<td class="dept"><span class="dept-dot" style="background:'+colors[d.name]+'"></span>'+esc(d.name)+'<span class="dept-meta">секции/студии: '+fmt(d.studio)+'</span></td>'+
      '<td class="num">'+fmt(d.clients)+'</td><td class="num">'+fmt(d.pt)+'<span class="metric-sub">'+fmt(d.pt_clients)+' уник.</span></td>'+
      '<td class="num grp-sep">'+mln(d.real)+'</td><td>'+pill(d.real_pct)+'</td><td class="num">'+mln(d.prev)+'</td><td>'+delta(d.delta_pct)+'</td>'+
      '<td class="num grp-sep">'+(d.st!=null?d.st+'<span class="st-conv">план '+d.st_plan+'</span>':'<span class="muted">—</span>')+'</td><td>'+pill(d.st_pct)+'</td></tr>';}).join('');
    var t=D.totals;
    table.innerHTML='<thead><tr class="grp"><th class="dept-h"></th><th>Клиенты</th><th>ПТ</th><th colspan="4" class="grp-sep">Реализация</th><th colspan="2" class="grp-sep">СТ</th></tr>'+
      '<tr><th class="dept-h">Департамент</th><th>уник.</th><th>шт / уник.</th><th class="grp-sep">млн ₽</th><th>% плана</th><th>Прошлый год</th><th>Δ</th><th class="grp-sep">Кол-во</th><th>% плана</th></tr></thead><tbody>'+rows+'</tbody>'+
      '<tfoot><tr><td class="dept">ФД — итого<span class="dept-meta">секции/студии: '+fmt(t.studio)+'</span></td><td class="num">'+fmt(t.clients)+'</td><td class="num">'+fmt(t.pt)+'<span class="metric-sub">'+fmt(t.pt_clients)+' уник.</span></td>'+
      '<td class="num grp-sep">'+mln(t.real)+'</td><td>'+pill(t.real_pct)+'</td><td class="num">'+mln(t.prev)+'</td><td>'+delta(t.delta_pct)+'</td><td class="num grp-sep">'+t.st+'<span class="st-conv">план '+t.st_plan+'</span></td><td>'+pill(t.st_pct)+'</td></tr></tfoot>';
    var hero=document.querySelector('.hero-cells .hero-cell:nth-child(2) .hero-big');
    if(hero) hero.insertAdjacentHTML('afterend','<div class="hero-cap num">'+fmt(t.pt_clients)+' уник.</div>');
    var note=document.getElementById('footNote');
    if(note) note.textContent+=' Уникальные клиенты — по ID в FIO; секции/студии — сумма Qty услуг со словами «Секция» или «Студия».';
  }
  var css=document.createElement('style');
  css.textContent='.dept-meta,.metric-sub{display:block;font-size:9px;color:var(--text-3);font-weight:600;margin-top:1px}.dept-meta{margin-left:16px}.lb-grid .lb-col{gap:4px}.rank-list{gap:2.6px}@media(max-width:899px){table{min-width:760px}}';
  document.head.appendChild(css);
  setTimeout(enhance,0);
  window.addEventListener('load',enhance);
})();

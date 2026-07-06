// Persist language selection to localStorage and cookie when language links are clicked
document.addEventListener('click', function(e){
  var a = e.target.closest && e.target.closest('a');
  if(!a) return;
  try{
    var href = a.getAttribute('href')||'';
    if(href.indexOf('?language=')!==-1){
      var m = href.match(/[?&]language=([^&]+)/);
      if(m){
        var lang = decodeURIComponent(m[1]);
        localStorage.setItem('site_language', lang);
        document.cookie = 'site_language='+lang+'; path=/; max-age='+(60*60*24*365);
      }
    }
  }catch(err){}
});

// On load, if localStorage has language, but cookie not present, set cookie
try{
  var ls = localStorage.getItem('site_language');
  if(ls && document.cookie.indexOf('site_language=')===-1){
    document.cookie = 'site_language='+ls+'; path=/; max-age='+(60*60*24*365);
  }
}catch(e){}

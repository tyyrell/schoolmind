document.addEventListener('DOMContentLoaded', function(){
  var slider = document.querySelector('[data-slider]');
  if (!slider) return;
  var track = slider.querySelector('[data-slider-track]');
  var cards = Array.from(slider.querySelectorAll('.slider-card'));
  var prev = slider.querySelector('.slider-arrow.prev');
  var next = slider.querySelector('.slider-arrow.next');
  var dotsWrapper = slider.querySelector('.slider-dots');
  var labelTemplate = slider.dataset.slideLabelTemplate || 'Slide {n}';
  var currentIndex = 0;
  var timeoutId = null;
  var delay = 2800;
  var isTouching = false;
  var startX = 0;
  var currentTranslate = 0;

  function updateSlide(index, animate) {
    currentIndex = (index + cards.length) % cards.length;
    track.style.transition = animate ? 'transform 0.75s ease' : 'none';
    track.style.transform = 'translateX(' + (-currentIndex * 100) + '%)';
    dotsWrapper.querySelectorAll('.slider-dot').forEach(function(dot, dotIndex) {
      dot.classList.toggle('active', dotIndex === currentIndex);
      dot.setAttribute('aria-pressed', dotIndex === currentIndex ? 'true' : 'false');
    });
  }

  function scheduleNext() {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(function() {
      updateSlide(currentIndex + 1, true);
      scheduleNext();
    }, delay);
  }

  function createDots() {
    cards.forEach(function(_, index) {
      var dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'slider-dot';
      dot.setAttribute('aria-label', labelTemplate.replace('{n}', index + 1));
      dot.setAttribute('aria-pressed', 'false');
      dot.addEventListener('click', function() {
        updateSlide(index, true);
        scheduleNext();
      });
      dotsWrapper.appendChild(dot);
    });
  }

  function onTouchStart(event) {
    isTouching = true;
    startX = event.touches ? event.touches[0].clientX : event.clientX;
    currentTranslate = -currentIndex * slider.offsetWidth;
    track.style.transition = 'none';
    clearTimeout(timeoutId);
  }

  function onTouchMove(event) {
    if (!isTouching) return;
    var currentX = event.touches ? event.touches[0].clientX : event.clientX;
    var delta = currentX - startX;
    track.style.transform = 'translateX(' + (currentTranslate + delta) + 'px)';
  }

  function onTouchEnd(event) {
    if (!isTouching) return;
    isTouching = false;
    var endX = event.changedTouches ? event.changedTouches[0].clientX : event.clientX;
    var moved = endX - startX;
    if (Math.abs(moved) > 60) {
      if (moved < 0) {
        updateSlide(currentIndex + 1, true);
      } else {
        updateSlide(currentIndex - 1, true);
      }
    } else {
      updateSlide(currentIndex, true);
    }
    scheduleNext();
  }

  createDots();
  updateSlide(0, false);
  scheduleNext();

  if (prev) {
    prev.addEventListener('click', function() {
      updateSlide(currentIndex - 1, true);
      scheduleNext();
    });
  }
  if (next) {
    next.addEventListener('click', function() {
      updateSlide(currentIndex + 1, true);
      scheduleNext();
    });
  }

  slider.addEventListener('keydown', function(event) {
    if (event.key === 'ArrowLeft') {
      updateSlide(currentIndex - 1, true);
      scheduleNext();
    }
    if (event.key === 'ArrowRight') {
      updateSlide(currentIndex + 1, true);
      scheduleNext();
    }
  });

  slider.addEventListener('mouseenter', function() {
    clearTimeout(timeoutId);
  });
  slider.addEventListener('mouseleave', function() {
    scheduleNext();
  });

  slider.addEventListener('touchstart', onTouchStart, { passive: true });
  slider.addEventListener('touchmove', onTouchMove, { passive: true });
  slider.addEventListener('touchend', onTouchEnd);
  slider.addEventListener('mousedown', onTouchStart);
  slider.addEventListener('mousemove', onTouchMove);
  slider.addEventListener('mouseup', onTouchEnd);
});

var homepageSliderImages = [
  { file: '01_ai_assisted_student_support.png', target: '#top', alt: 'AI assisted student support dashboard' },
  { file: '02_organized_counselor_workflows.png', target: '#product', alt: 'Organized counselor workflows dashboard' },
  { file: '03_understand_classroom_pulse.png', target: '#product', alt: 'Classroom pulse and teacher insights dashboard' },
  { file: '04_interactive_learning_experiences.png', target: '#teacher-insights', alt: 'Interactive learning experiences dashboard' },
  { file: '05_privacy_first_school_platform.png', target: '#trust', alt: 'Privacy first school platform dashboard' },
  { file: '06_start_your_30_day_free_trial.png', target: '#start-experience', alt: 'Start your 30 day free trial' },
  { file: '07_teacher_ready_insights.png', target: '#teacher-insights', alt: 'Teacher ready insights dashboard' },
  { file: '08_school_leaders_overview.png', target: '#school-leaders', alt: 'School leaders overview dashboard' },
  { file: '09_stronger_parent_communication.png', target: '#parent-communication', alt: 'Stronger parent communication dashboard' },
  { file: '10_early_alerts_timely_support.png', target: '#early-alerts', alt: 'Early alerts and timely support dashboard' },
  { file: '11_student_check_ins_that_actually_help.png', target: '#top', alt: 'Student check-ins dashboard' },
  { file: '12_parent_consent_made_simple.png', target: '#trust', alt: 'Parent consent made simple dashboard' },
  { file: '13_role_based_school_workspaces.png', target: '#product', alt: 'Role-based school workspaces dashboard' },
  { file: '14_attendance_with_actionable_follow_up.png', target: '#early-alerts', alt: 'Attendance actionable follow-up dashboard' },
  { file: '15_support_plans_that_move_forward.png', target: '#product', alt: 'Support plans that move forward dashboard' },
  { file: '16_one_platform_for_two_languages.png', target: '#top', alt: 'One platform for two languages dashboard' },
  { file: '17_try_the_demo_before_you_sign_in.png', target: '#start-experience', alt: 'Try the demo before you sign in dashboard' },
  { file: '18_wellbeing_signals_in_real_time.png', target: '#teacher-insights', alt: 'Wellbeing signals in real time dashboard' },
  { file: '19_teachers_and_counselors_working_together.png', target: '#teacher-insights', alt: 'Teachers and counselors working together dashboard' },
  { file: '20_reports_you_can_act_on.png', target: '#school-leaders', alt: 'Reports you can act on dashboard' },
];

function getSliderImagePath(fileName) {
  return '/static/images/home-slider/en/' + fileName;
}

function initSchoolMindHomeSlider() {
  var slider = document.querySelector('[data-sm-home-slider]');
  if (!slider) return;

  var track = slider.querySelector('[data-sm-slider-track]');
  var prev = slider.querySelector('[data-sm-slider-prev]');
  var next = slider.querySelector('[data-sm-slider-next]');
  var dotsWrap = slider.querySelector('[data-sm-slider-dots]');
  if (!track || !dotsWrap) return;

  var slides = homepageSliderImages.map(function(item, index) {
    var link = document.createElement('a');
    link.className = 'sm-home-slider-slide';
    link.href = item.target;
    link.setAttribute('aria-label', item.alt);
    link.dataset.slideIndex = String(index);

    var img = document.createElement('img');
    img.src = getSliderImagePath(item.file);
    img.alt = item.alt;
    img.loading = index === 0 ? 'eager' : 'lazy';
    img.decoding = 'async';

    link.appendChild(img);
    track.appendChild(link);

    var dot = document.createElement('button');
    dot.className = 'sm-home-slider-dot';
    dot.type = 'button';
    dot.setAttribute('aria-label', 'Go to slide ' + (index + 1));
    dot.addEventListener('click', function() {
      goToSlide(index, true);
    });
    dotsWrap.appendChild(dot);

    return { link: link, img: img, dot: dot };
  });

  var activeIndex = 0;
  var timer = null;
  var intervalMs = 2800;

  function render() {
    track.style.transform = 'translateX(-' + (activeIndex * 100) + '%)';
    slides.forEach(function(slide, index) {
      slide.dot.classList.toggle('is-active', index === activeIndex);
      slide.link.setAttribute('aria-hidden', index === activeIndex ? 'false' : 'true');
    });
  }

  function goToSlide(index, userAction) {
    activeIndex = (index + slides.length) % slides.length;
    render();
    if (userAction) {
      restartAutoSlide();
    }
  }

  function nextSlide(userAction) {
    goToSlide(activeIndex + 1, userAction);
  }

  function prevSlide(userAction) {
    goToSlide(activeIndex - 1, userAction);
  }

  function startAutoSlide() {
    stopAutoSlide();
    timer = window.setInterval(function() {
      nextSlide(false);
    }, intervalMs);
  }

  function stopAutoSlide() {
    if (timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  function restartAutoSlide() {
    stopAutoSlide();
    startAutoSlide();
  }

  if (prev) prev.addEventListener('click', function() { prevSlide(true); });
  if (next) next.addEventListener('click', function() { nextSlide(true); });

  slider.addEventListener('mouseenter', stopAutoSlide);
  slider.addEventListener('mouseleave', startAutoSlide);

  var touchStartX = 0;
  slider.addEventListener('touchstart', function(event) {
    touchStartX = event.changedTouches[0].clientX;
  }, { passive: true });
  slider.addEventListener('touchend', function(event) {
    var touchEndX = event.changedTouches[0].clientX;
    var delta = touchEndX - touchStartX;
    if (Math.abs(delta) > 45) {
      if (delta > 0) prevSlide(true);
      else nextSlide(true);
    }
  }, { passive: true });

  document.addEventListener('keydown', function(event) {
    if (event.key === 'ArrowLeft') prevSlide(true);
    if (event.key === 'ArrowRight') nextSlide(true);
  });

  render();
  startAutoSlide();
}

document.addEventListener('DOMContentLoaded', initSchoolMindHomeSlider);

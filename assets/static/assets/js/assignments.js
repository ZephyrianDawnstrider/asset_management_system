(() => {
  const forms = document.querySelectorAll('.js-assignment-action');
  forms.forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      const feedback = form.querySelector('.action-feedback');
      if (button) button.disabled = true;
      if (feedback) feedback.textContent = 'Saving assignment…';
      try {
        const response = await fetch(form.action, {
          method: 'POST',
          body: new FormData(form),
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        if (!response.headers.get('content-type')?.includes('application/json')) {
          throw new Error(response.redirected
            ? 'Your session may have expired. Sign in again, then retry.'
            : 'The server returned an unexpected response. Refresh the page and try again.');
        }
        const result = await response.json();
        if (!response.ok || !result.success) {
          throw new Error(result.message || 'The request could not be completed. Refresh and try again.');
        }
        if (feedback) feedback.textContent = result.message || form.dataset.success || 'Saved.';
        window.setTimeout(() => window.location.reload(), 700);
      } catch (error) {
        if (feedback) feedback.textContent = error.message || 'A network error prevented the change. Check your connection and try again.';
        if (button) button.disabled = false;
      }
    });
  });
})();

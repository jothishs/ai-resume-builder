// Client‑side script for the Flask resume builder app.  Handles dynamic
// form sections, collects input, saves drafts to localStorage,
// communicates with the backend to generate resumes and lists existing
// resumes.

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('resumeForm');
  const experienceContainer = document.getElementById('experienceContainer');
  const educationContainer = document.getElementById('educationContainer');
  const resultDiv = document.getElementById('result');
  const resumeList = document.getElementById('resumeList');

  // Add new experience input block
  function addExperience() {
    const wrapper = document.createElement('div');
    wrapper.className = 'experience-item';
    wrapper.innerHTML = `
      <input type="text" placeholder="Position" class="exp-position" required>
      <input type="text" placeholder="Company" class="exp-company" required>
      <input type="text" placeholder="Start Date" class="exp-start">
      <input type="text" placeholder="End Date" class="exp-end">
      <textarea placeholder="Description" class="exp-description"></textarea>
      <button type="button" class="btn secondary remove-exp">Remove</button>
    `;
    wrapper.querySelector('.remove-exp').addEventListener('click', () => {
      wrapper.remove();
    });
    experienceContainer.appendChild(wrapper);
  }

  // Add new education input block
  function addEducation() {
    const wrapper = document.createElement('div');
    wrapper.className = 'education-item';
    wrapper.innerHTML = `
      <input type="text" placeholder="Degree" class="edu-degree" required>
      <input type="text" placeholder="Institution" class="edu-institution" required>
      <input type="text" placeholder="Start Date" class="edu-start">
      <input type="text" placeholder="End Date" class="edu-end">
      <textarea placeholder="Description" class="edu-description"></textarea>
      <button type="button" class="btn secondary remove-edu">Remove</button>
    `;
    wrapper.querySelector('.remove-edu').addEventListener('click', () => {
      wrapper.remove();
    });
    educationContainer.appendChild(wrapper);
  }

  document.getElementById('addExperience').addEventListener('click', addExperience);
  document.getElementById('addEducation').addEventListener('click', addEducation);

  // Collect data from form
  function collectResumeData() {
    const formData = new FormData(form);
    const resume = {
      personal: {
        name: formData.get('name').trim(),
        email: formData.get('email').trim(),
        phone: formData.get('phone').trim(),
        address: formData.get('address').trim(),
      },
      summary: formData.get('summary').trim(),
      skills: [],
      experience: [],
      education: [],
    };
    const skillsRaw = formData.get('skills') || '';
    resume.skills = skillsRaw
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    // Experience
    const expItems = experienceContainer.querySelectorAll('.experience-item');
    expItems.forEach((item) => {
      const position = item.querySelector('.exp-position').value.trim();
      const company = item.querySelector('.exp-company').value.trim();
      const startDate = item.querySelector('.exp-start').value.trim();
      const endDate = item.querySelector('.exp-end').value.trim();
      const description = item.querySelector('.exp-description').value.trim();
      if (position || company || description) {
        resume.experience.push({ position, company, startDate, endDate, description });
      }
    });
    // Education
    const eduItems = educationContainer.querySelectorAll('.education-item');
    eduItems.forEach((item) => {
      const degree = item.querySelector('.edu-degree').value.trim();
      const institution = item.querySelector('.edu-institution').value.trim();
      const startDate = item.querySelector('.edu-start').value.trim();
      const endDate = item.querySelector('.edu-end').value.trim();
      const description = item.querySelector('.edu-description').value.trim();
      if (degree || institution || description) {
        resume.education.push({ degree, institution, startDate, endDate, description });
      }
    });
    return resume;
  }

  // Load existing resumes
  async function loadResumes() {
    resumeList.innerHTML = '';
    try {
      const res = await fetch('/api/resumes');
      const data = await res.json();
      if (Array.isArray(data)) {
        data.forEach((entry) => {
          const li = document.createElement('li');
          const link = document.createElement('a');
          link.href = `/api/resumes/${entry.id}`;
          link.textContent = `Resume ${entry.id} (created ${new Date(entry.createdAt).toLocaleString()})`;
          link.target = '_blank';
          li.appendChild(link);
          resumeList.appendChild(li);
        });
      }
    } catch (err) {
      console.error('Failed to load resumes', err);
    }
  }

  // Submit handler
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const resumeData = collectResumeData();
    localStorage.setItem('resumeDraft', JSON.stringify(resumeData));
    resultDiv.innerHTML = '<p>Generating resume…</p>';
    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(resumeData)
      });
      const data = await res.json();
      if (res.ok) {
        resultDiv.innerHTML = `<p>Resume created successfully. <a href="${data.pdfUrl}" target="_blank">Download PDF</a></p>`;
        loadResumes();
      } else {
        resultDiv.innerHTML = `<p style="color:red;">Error: ${data.error || 'Unknown error'}</p>`;
      }
    } catch (err) {
      resultDiv.innerHTML = `<p style="color:red;">Failed to generate resume: ${err.message}</p>`;
    }
  });

  // Load draft from localStorage
  function loadDraft() {
    const draft = localStorage.getItem('resumeDraft');
    if (!draft) return;
    try {
      const data = JSON.parse(draft);
      if (data.personal) {
        form.elements['name'].value = data.personal.name || '';
        form.elements['email'].value = data.personal.email || '';
        form.elements['phone'].value = data.personal.phone || '';
        form.elements['address'].value = data.personal.address || '';
      }
      form.elements['summary'].value = data.summary || '';
      form.elements['skills'].value = (data.skills || []).join(', ');
      (data.experience || []).forEach((exp) => {
        addExperience();
        const item = experienceContainer.lastElementChild;
        item.querySelector('.exp-position').value = exp.position || '';
        item.querySelector('.exp-company').value = exp.company || '';
        item.querySelector('.exp-start').value = exp.startDate || '';
        item.querySelector('.exp-end').value = exp.endDate || '';
        item.querySelector('.exp-description').value = exp.description || '';
      });
      (data.education || []).forEach((edu) => {
        addEducation();
        const item = educationContainer.lastElementChild;
        item.querySelector('.edu-degree').value = edu.degree || '';
        item.querySelector('.edu-institution').value = edu.institution || '';
        item.querySelector('.edu-start').value = edu.startDate || '';
        item.querySelector('.edu-end').value = edu.endDate || '';
        item.querySelector('.edu-description').value = edu.description || '';
      });
    } catch (err) {
      console.error('Failed to load draft', err);
    }
  }

  loadDraft();
  loadResumes();
});

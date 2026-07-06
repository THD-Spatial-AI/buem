# Contributing to BuEM Documentation

Thank you for your interest in contributing to the BuEM documentation! This guide outlines how to contribute effectively.

## Documentation Structure

The BuEM documentation is organized as follows:

- `docs/source/introduction/` - Project overview and introduction
- `docs/source/api_integration/` - API integration guide for developers
- `docs/source/model_attributes/` - Complete reference of building attributes
- `docs/source/technical/` - In-depth technical documentation
- `docs/source/installation/` - Setup and deployment instructions
- `docs/source/examples/` - Practical examples and use cases

## Getting Started

### Prerequisites

- Python 3.8+ with conda environment
- Git for version control
- Text editor or IDE with reStructuredText support

### Setting Up Development Environment

1. Clone the repository:

   ```bash
   git clone <buem-repository-url>
   cd buem
   ```

1. Set up conda environment:

   ```bash
   conda env create -f environment.yml
   conda activate buem_env
   ```

1. Install documentation dependencies:

   ```bash
   pip install -r docs/requirements.txt
   ```

1. Build documentation locally:

   ```bash
   cd docs
   make html
   ```

The built documentation will be available in `docs/build/html/index.html`.

## Documentation Standards

### Writing Style

- **Audience**: Focus on developers integrating BuEM with other systems
- **Clarity**: Use clear, concise language avoiding unnecessary jargon
- **Structure**: Follow logical information hierarchy with proper headings
- **Examples**: Include practical code examples whenever possible

### reStructuredText Guidelines

- Use consistent heading styles:

  ```rst
  Page Title
  ==========

  Major Section
  -------------

  Subsection
  ~~~~~~~~~~
  ```

- Format code blocks with proper syntax highlighting:

  ```rst
  .. code-block:: python

      import requests
      response = requests.get('http://localhost:5000/api/health')
  ```

- Use tables for structured information:

  ```rst
  .. list-table::
     :header-rows: 1
     :widths: 25 25 50

     * - Parameter
       - Type
       - Description
     * - latitude
       - number
       - Geographic latitude (-90 to 90)
  ```

### API Documentation Standards

- **Complete Examples**: Every API endpoint should have complete request/response examples
- **Error Cases**: Document error responses and common failure scenarios
- **Integration Focus**: Emphasize how to integrate with other systems
- **Data Formats**: Clearly specify input/output data structures

### Code Examples

- **Runnable**: All code examples should be complete and runnable
- **Error Handling**: Include proper error handling in examples
- **Comments**: Add comments explaining non-obvious code sections
- **Multiple Languages**: Provide examples in different programming languages when relevant

## Contribution Process

### 1. Issue Creation

Before making changes, create an issue describing:

- What documentation needs to be added/changed
- Why the change is needed
- Target audience for the content

### 2. Branch Creation

Create a feature branch for your changes:

```bash
git checkout -b feature/document-new-feature
```

### 3. Making Changes

- Edit `.rst` files using any text editor
- Build documentation locally to test changes:

  ```bash
  cd docs
  make html
  ```

- Review the output in `docs/build/html/`

### 4. Testing

Before submitting:

- **Build Test**: Ensure `make html` completes without errors
- **Link Check**: Verify all internal references work
- **Content Review**: Check for spelling, grammar, and technical accuracy
- **Example Verification**: Test all code examples

### 5. Pull Request Submission

Submit a pull request with:

- Clear description of changes
- Reference to related issue(s)
- Screenshots of rendered documentation changes (if applicable)

## Review Process

### Reviewer Checklist

Documentation reviewers should verify:

- [ ] Technical accuracy of content
- [ ] Completeness of API documentation
- [ ] Code examples are runnable and correct
- [ ] Formatting follows documentation standards
- [ ] Changes align with target audience needs
- [ ] Links and references work properly

### Approval Criteria

Pull requests are approved when:

- Technical review is complete
- Documentation builds successfully
- Content meets style guidelines
- All feedback has been addressed

## Specific Contribution Areas

### API Integration Documentation

**High Priority Areas**:

- Authentication and security examples
- Error handling patterns
- Performance optimization guidance
- Real-world integration scenarios

**Requirements**:

- Must include complete, runnable examples
- Should cover both success and error cases
- Must be Docker-container focused for deployment

### Model Attributes Documentation

**Focus Areas**:

- Building component specifications
- Validation rules and constraints
- Data exchange formats
- Integration with external building databases

**Requirements**:

- Precise technical specifications
- Clear examples of valid/invalid values
- Cross-references between related attributes

### Examples and Use Cases

**Needed Examples**:

- Industry-specific use cases
- Multi-building batch processing
- Integration with specific platforms
- Performance optimization techniques

**Requirements**:

- Complete, working code examples
- Real-world scenarios
- Step-by-step instructions
- Expected outputs and results

## Documentation Maintenance

### Regular Updates

Documentation should be updated when:

- API endpoints change
- New features are added
- Building attribute specifications change
- Integration patterns evolve

### Version Management

- Documentation versions follow software releases
- Breaking changes require clear migration guides
- Deprecated features need sunset timelines

## Versioning

BuEM follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
All notable changes are recorded in [`CHANGELOG.md`](CHANGELOG.md).

```text
 MAJOR . MINOR . PATCH
   │       │       └─── docs, bugfixes, refactors (no API change)
   │       └─────────── new features (backwards-compatible)
   └─────────────────── breaking changes
```

**Examples:**

```text
 1.0.0 → 1.0.1   fix: corrected unit conversion in thermal model
 1.0.1 → 1.1.0   feat: added multi-building batch processing
 1.1.0 → 2.0.0   breaking: renamed API endpoints, changed response format
```

When bumping a version:

1. Add an entry to `CHANGELOG.md` under the new version heading.
1. Tag the commit: `git tag v1.0.2 && git push --tags`.

### Quality Assurance

Monthly quality checks should verify:

- All examples still work with current API
- Links and references remain valid
- Content accuracy against latest codebase
- User feedback has been incorporated

## Contact and Support

For documentation questions:

- Create an issue in the repository
- Tag documentation maintainers in pull requests
- Use descriptive issue titles and clear descriptions

## Recognition

Contributors will be recognized by:

- Attribution in documentation credits
- Mention in release notes for significant contributions
- Invitation to documentation review team for regular contributors

Thank you for helping make BuEM documentation better for developers integrating building energy models!
